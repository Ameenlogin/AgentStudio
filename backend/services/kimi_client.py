"""Async wrapper over the OpenAI-compatible NVIDIA NIM endpoint with a built-in
streaming circuit breaker, key-pool rotation and endpoint health routing.

Kimi K2.x models on NVIDIA NIM have *reasoning enabled by default*: the final
answer only arrives in ``delta.content`` after the reasoning trace finishes,
and the trace itself is streamed in ``delta.reasoning`` / ``delta.reasoning_content``.
For the fast conversational path we disable reasoning via
``chat_template_kwargs={"thinking": false}`` so a short answer returns
immediately. If a given model rejects that kwarg we transparently retry once
without it.

Circuit breaker
---------------
``stream_guarded`` yields raw streaming chunks but watches inter-chunk latency.
The breaker exists to recover from a genuinely *dead* connection — NOT to police
the normal pauses a reasoning model takes between chunks (which can be many
seconds). So the idle timeouts are deliberately generous:

  * before the first token — ``FIRST_CHUNK_TIMEOUT`` — a slow/dead connection at
    open time is retried cleanly on an alternate key/endpoint (no output lost).
  * mid-stream — ``CHUNK_STALL_TIMEOUT`` — only a long silence (dead socket)
    trips it; it then raises ``StreamInterrupted`` which the agent loop recovers
    from (retry the step if nothing usable was produced, otherwise finish with
    what arrived) instead of surfacing a scary error.
"""
import time
import asyncio
from openai import AsyncOpenAI
from services.api_pool import APIPool

# Idle (inter-chunk) timeouts. These must be larger than a reasoning model's
# normal think-pause or we would kill healthy streams ("Stream interrupted").
CHUNK_STALL_TIMEOUT = 60.0   # mid-stream silence that means a dead connection
FIRST_CHUNK_TIMEOUT = 120.0  # first-token budget (reasoning models are slow to start)
MAX_BREAKER_RETRIES = 2      # alternate-endpoint retries before giving up

# Models that don't accept the NIM ``chat_template_kwargs={"thinking": …}`` kwarg
# (instruct / non-reasoning checkpoints such as qwen3-*-instruct or llama-*-instruct).
# Sending it to them returns a 400 and forces a wasted retry without it on EVERY
# turn — which is exactly why such models felt "stupidly slow". We seed the obvious
# ones and also learn any model at runtime the first time it rejects the kwarg, so
# we never pay that failed round-trip more than once.
_NO_THINKING: set[str] = set()


def _supports_thinking(model: str) -> bool:
    m = (model or "").lower()
    if m in _NO_THINKING:
        return False
    # Instruct / chat checkpoints have no separate reasoning channel.
    if "instruct" in m or "-chat" in m:
        return False
    return True


class StreamStalled(Exception):
    """Stream died before producing anything — safe to retry cleanly."""


class StreamInterrupted(Exception):
    """Stream died mid-output — the agent loop decides how to recover."""


class KimiClient:
    """Wraps either a single key or an APIPool for rate-limit-aware requests."""

    def __init__(self, *, api_key: str = "", base_url: str = "https://integrate.api.nvidia.com/v1",
                 model_name: str = "moonshotai/kimi-k2.6", pool: APIPool | None = None):
        self.model_name = model_name
        self.pool = pool
        self.base_url = base_url
        if not pool:
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = None  # will use pool.acquire()

    def _build_kwargs(self, messages, tools, temperature, thinking):
        kwargs = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            "max_tokens": 16384,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        extra_body = None
        # Only send the reasoning kwarg to models that actually accept it — this
        # avoids a guaranteed 400-then-retry on every instruct-model turn.
        if thinking is not None and _supports_thinking(self.model_name):
            extra_body = {"chat_template_kwargs": {"thinking": bool(thinking)}}
        return kwargs, extra_body

    async def _open_stream(self, kwargs, extra_body):
        """Open one stream, returning (stream, slot, endpoint). Handles the
        thinking-kwarg fallback and 429 backoff."""
        slot = None
        endpoint = None
        call_kwargs = dict(kwargs)
        if extra_body is not None:
            call_kwargs["extra_body"] = extra_body
        try:
            if self.pool:
                slot = await self.pool.acquire()
                endpoint = self.pool.router.best()
                client = slot.client_for(endpoint.base_url)
                return await client.chat.completions.create(**call_kwargs), slot, endpoint
            return await self.client.chat.completions.create(**call_kwargs), None, None
        except Exception as e:
            err = str(e).lower()
            # 1) Model rejected the thinking kwarg — remember that, drop it, retry.
            if extra_body is not None and ("400" in err or "chat_template" in err
                                           or "unexpected" in err or "extra" in err):
                _NO_THINKING.add((self.model_name or "").lower())
                return await self._open_stream(kwargs, None)
            # 2) Model doesn't support function calling — drop tools and retry so
            #    every model in the picker still produces an answer.
            if ("tool" in err or "function" in err) and "tools" in kwargs and (
                    "400" in err or "not support" in err or "invalid" in err
                    or "unsupported" in err or "does not" in err):
                stripped = {k: v for k, v in kwargs.items() if k not in ("tools", "tool_choice")}
                return await self._open_stream(stripped, extra_body)
            if "429" in err or "rate" in err:
                if self.pool and slot:
                    self.pool.handle_rate_limit(slot)
            if self.pool and slot:
                slot.record_error()
            if endpoint:
                endpoint.record_failure()
            raise

    async def stream_guarded(self, messages, tools=None, temperature=0.6,
                             thinking: bool | None = None):
        """Async generator of streaming chunks, protected by the circuit breaker.

        Retries on an alternate key/endpoint only while nothing has been emitted
        yet, so the user never sees duplicated output."""
        kwargs, extra_body = self._build_kwargs(messages, tools, temperature, thinking)
        last_err: Exception | None = None

        for attempt in range(MAX_BREAKER_RETRIES + 1):
            try:
                stream, slot, endpoint = await self._open_stream(kwargs, extra_body)
            except Exception as e:
                last_err = e
                if attempt < MAX_BREAKER_RETRIES:
                    await asyncio.sleep(min(2 ** attempt, 4))
                    continue
                raise

            produced = False
            started = time.monotonic()
            it = stream.__aiter__()
            try:
                while True:
                    timeout = CHUNK_STALL_TIMEOUT if produced else FIRST_CHUNK_TIMEOUT
                    try:
                        chunk = await asyncio.wait_for(it.__anext__(), timeout=timeout)
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        # Breaker trips only on a long silence (dead socket).
                        if slot:
                            slot.record_error()
                        if endpoint:
                            endpoint.record_failure()
                        if not produced and attempt < MAX_BREAKER_RETRIES:
                            raise StreamStalled()  # nothing emitted — retry cleanly
                        raise StreamInterrupted()  # mid-output — let the loop recover

                    if not produced:
                        produced = True
                        if endpoint:
                            endpoint.record_latency(time.monotonic() - started)
                    yield chunk

                if slot:
                    slot.record_success()
                return
            except StreamStalled:
                last_err = StreamStalled()
                continue  # retry on the next-healthiest endpoint/key
            finally:
                try:
                    await stream.close()
                except Exception:
                    pass

        if last_err:
            raise last_err

    async def stream(self, messages, tools=None, temperature=0.6,
                     max_retries=2, thinking: bool | None = None):
        """Back-compat: open a single guarded stream and return it as an async
        iterator. New code should iterate ``stream_guarded`` directly."""
        return self.stream_guarded(messages, tools=tools, temperature=temperature,
                                   thinking=thinking)


def extract_reasoning(delta) -> str | None:
    """Pull a reasoning trace out of a streamed delta regardless of which field
    the NVIDIA model uses (reasoning_content vs reasoning), including the
    pydantic model_extra bucket where the OpenAI SDK stashes unknown fields."""
    for attr in ("reasoning_content", "reasoning"):
        v = getattr(delta, attr, None)
        if v:
            return v
    extra = getattr(delta, "model_extra", None)
    if isinstance(extra, dict):
        return extra.get("reasoning_content") or extra.get("reasoning")
    return None
