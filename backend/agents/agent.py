"""The agent loop. Streams an NDJSON event protocol to the frontend:

  {"type":"reasoning",   "delta":"..."}        # model thinking tokens
  {"type":"content",     "delta":"..."}        # answer tokens
  {"type":"permission_request","id","call_id","name","label","kind","args"}
  {"type":"tool_start",  "id","name","label","icon","kind","args"[,"agent"]}
  {"type":"tool_stream", "id","delta":"..."[,"agent"]}   # live stdout/stderr
  {"type":"tool_result", "id","ok":true,"result":"..."[,"agent"]}
  {"type":"cache_hit",   "similarity":0.97}     # answered from semantic cache
  {"type":"swarm_plan",  "plan","subtasks":[...]}
  {"type":"swarm_agent", "id","role","title","status"}
  {"type":"heartbeat"}                          # keep-alive while awaiting input
  {"type":"done"}
  {"type":"error",       "error":"..."}
  {"type":"swarm_status","agents":[...],"total_rpm":x,"total_limit":y}

Execution modes (chosen by ``router``):
  - simple  : one streaming reply, no tools, served from the semantic cache when
              a near-identical question was answered before.
  - agentic : the full plan->act->observe loop with the workspace toolkit, with
              parallel read-only tool calls and live tool-output streaming.
  - swarm   : (complex tasks) Planner -> parallel research workers -> builder ->
              synthesizer, orchestrated in agents/orchestrator.py.
"""
import json
import asyncio
import datetime
import hashlib
import os
from services.kimi_client import KimiClient, extract_reasoning
from services.api_pool import APIPool
from services.cache import cache
from services import skills as skills_service
from tools.tool_router import (
    AVAILABLE_TOOLS, TOOL_META, RISKY_KINDS, execute_tool,
    execute_tool_streaming, is_parallel_safe, STREAMING_DISPATCH,
)
from tools import permissions
from tools.sandbox import get_workspace
from agents import router
from agents.summarizer import prune_context, summarize_history


def _ev(obj) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"


def _now_str() -> str:
    now = datetime.datetime.now().astimezone()
    return now.strftime("%A, %B %d, %Y at %I:%M %p %Z").strip()


def _env_preamble() -> str:
    """Live environment facts injected every turn so the model never guesses the
    date and always knows it can reach the internet and the local workspace."""
    return (
        f"ENVIRONMENT\n"
        f"- Current local date & time: {_now_str()}. Use this for any 'today / now / "
        f"current date or time' question — do NOT guess or say you don't know.\n"
        f"- Working directory (you can read & write here): {get_workspace()}\n"
        f"- You have full internet access via web_search, fetch_url, scrape and "
        f"http_request. For anything live or after your training cutoff (news, prices, "
        f"versions, weather, events), search the web and report what you find.\n\n"
    )


def _compose_system(base: str) -> str:
    """Final system prompt = live environment + base instructions + installed skills."""
    parts = [_env_preamble(), base]
    sk = skills_service.skills_prompt()
    if sk:
        parts.append("\n\n" + sk)
    return "".join(parts)


# Agentic-mode system prompt: act when needed, answer directly when not.
_AGENT_SYSTEM = (
    "You are Agent Studio, an elite autonomous software-and-research agent that "
    "outperforms conventional coding assistants. You build complete, production-"
    "quality software and ship it.\n\n"
    "TOOLKIT (all sandboxed to the user's workspace):\n"
    "- Files: read/write/edit/append/move/copy/delete, batch read/write, recursive "
    "tree view, search and bulk-replace, precise unified-diff `apply_patch`.\n"
    "- Archives: create/extract/list zips AND in-place zip editing "
    "(zip_read/zip_write/zip_edit/zip_remove) — write code straight into a .zip.\n"
    "- PDFs: pdf_read, pdf_info, pdf_create (from text/Markdown).\n"
    "- Code: run shell commands and Python with live streamed output; git.\n"
    "- Web: search, fetch, scrape (CSS selectors), extract links, HTTP, downloads.\n\n"
    "YOU CAN BUILD: full websites and web apps, frontend/backend systems, CLIs, "
    "scripts, data pipelines, WordPress themes & plugins (PHP), static sites, "
    "design assets (SVG/HTML/CSS), documents and PDFs — any file type.\n\n"
    "CHOOSING THE RIGHT TOOL (always pick one and act — never say you can't):\n"
    "- Current date/time → it's given in ENVIRONMENT above; just answer.\n"
    "- Live info (news, prices, latest versions, weather, anything recent) → "
    "web_search then fetch_url, and report findings.\n"
    "- Find files → glob_files; search file contents → grep; map a project → tree_directory.\n"
    "- Create or overwrite a file → write_file; precise edits → apply_patch or edit_file.\n"
    "- Edit files INSIDE a .zip without unzipping → zip_read / zip_write / zip_edit; "
    "build/extract archives → create_zip / extract_zip.\n"
    "- Read a PDF → pdf_read; make a PDF → pdf_create.\n"
    "- Run or test code → run_command / python_exec (output streams live).\n"
    "- A Python library is missing → install_package (e.g. pandas, pillow, lxml, "
    "playwright); then use it.\n"
    "- Drive ANY installed CLI via run_command: git, gh (GitHub), npm/pnpm/yarn, "
    "pip, docker, curl, etc. Clone repos, open PRs with gh, scaffold apps.\n"
    "- Install a skill from a GitHub repo → install_skill; consult one → read_skill.\n"
    "- Use git for version control; download_file / http_request for network I/O.\n\n"
    "HOW TO WORK:\n"
    "- Read the request first. If it can be answered directly (including current "
    "date/time from ENVIRONMENT), just answer concisely — no tools, no plan narration.\n"
    "- If it needs action, think briefly, then ACT: call tools, observe results, "
    "self-correct, and continue autonomously until the task is fully done and "
    "verified. Prefer doing over asking; only stop if genuinely blocked.\n"
    "- Batch related read-only calls in one turn (they run in parallel). Verify your "
    "work by running it. If a tool errors, read the error and try a different approach "
    "— do not give up or claim a capability is unavailable.\n"
    "- When asked to package or zip results, produce the artifact and confirm its "
    "path so the user can download it.\n\n"
    "LARGE FILES, BIG CODEBASES & DATABASES — you are fully equipped, never give up:\n"
    "- Never say a file or project is 'too big'. To read a huge file, call read_file "
    "with offset/limit to page through it by line range; use grep to jump straight to "
    "the relevant lines and glob_files / tree_directory to map a large project first.\n"
    "- Edit precisely instead of rewriting whole files: apply_patch (a unified diff "
    "that can change many files at once) and edit_file / patch_file for targeted "
    "changes. Reserve write_file for brand-new files or deliberate full rewrites.\n"
    "- Act on many files at once: batch_read_files, batch_write_files, and "
    "replace_in_files for project-wide find-and-replace — prefer this over editing "
    "one file at a time.\n"
    "- Work INSIDE archives without unpacking: zip_read / zip_write / zip_edit / "
    "zip_remove — ideal for large WordPress plugins/themes or any code shipped as a .zip.\n"
    "- For databases and data files, run real code: python_exec (sqlite3, pandas, "
    "openpyxl, …) and install_package for anything missing.\n"
    "- You have ALL of these capabilities right now — pick the most efficient tool for "
    "the job and use it. Favor batching and patching over slow one-edit-at-a-time work.\n\n"
    "KNOWING WHEN TO STOP (critical):\n"
    "- Produce each deliverable exactly ONCE. After you write a report, file, or "
    "answer, STOP — do not regenerate it, re-read it 'to double-check', or restate "
    "the same content again.\n"
    "- Never repeat a tool call you have already made with the same arguments — you "
    "already have that result earlier in the conversation.\n"
    "- The instant the task is complete, end your turn with a short final summary and "
    "NO further tool calls. Do not keep going after you are done; silence is correct "
    "when there is nothing new to do.\n"
    "Keep responses tight, well-formatted, and free of filler."
)


def _status_ev(pool):
    return _ev({
        "type": "swarm_status",
        "agents": pool.status(),
        "total_rpm": pool.total_rpm_used,
        "total_limit": pool.total_rpm_limit,
        "endpoints": pool.router.status(),
    })


async def run_agent(messages, *, api_keys, base_url, model_name,
                    temperature=0.6, system_prompt=None, max_steps=50,
                    tools_enabled=True, permission_mode="ask", swarm_mode="auto"):
    valid_keys = [k for k in api_keys if k and k.strip()]
    if not valid_keys:
        yield _ev({"type": "error",
                   "error": "No valid API keys configured. Open Settings and add your NVIDIA API key."})
        return

    pool = APIPool(valid_keys, base_url)
    client = KimiClient(pool=pool, base_url=base_url, model_name=model_name)

    mode = router.classify(messages) if tools_enabled else "simple"

    # -- FAST PATH ------------------------------------------------------------
    if mode == "simple":
        escalate = False
        async for ev in _run_simple(client, pool, messages, temperature, model_name):
            if ev == "__ESCALATE__":
                escalate = True
                break
            yield ev
        if not escalate:
            return
        # fall through to the full agent loop transparently

    # -- SWARM PATH (complex multi-part tasks) --------------------------------
    if tools_enabled and swarm_mode != "off" and router.is_complex(messages):
        from agents.orchestrator import run_swarm
        async for ev in run_swarm(
            messages, client=client, pool=pool, model_name=model_name,
            temperature=temperature, system_prompt=system_prompt,
            max_steps=max_steps, permission_mode=permission_mode,
        ):
            yield ev
        return

    # -- AGENTIC PATH ---------------------------------------------------------
    base_system = _compose_system(system_prompt or _AGENT_SYSTEM)
    convo = [{"role": "system", "content": base_system}]
    convo.extend(messages)

    tools = AVAILABLE_TOOLS if tools_enabled else None
    async for ev in agentic_loop(client, pool, convo, tools, temperature,
                                 max_steps, permission_mode):
        yield ev


import re as _re

def _clean_tool_name(name: str) -> str:
    """Strip artefacts some models leak into the function name.

    GPT-OSS uses the OpenAI 'harmony' format and can emit the channel marker
    inside the tool name, e.g. ``list_directory<|channel|>commentary`` — which
    makes dispatch fail on every tool. Keep only the leading valid identifier.
    """
    n = (name or "").strip()
    m = _re.match(r"[A-Za-z0-9_.\-]+", n)
    return m.group(0) if m else n


def _args_complete(args: str) -> bool:
    """A tool-call's streamed JSON args are usable if empty or fully parseable."""
    s = (args or "").strip()
    if not s:
        return True
    try:
        json.loads(s)
        return True
    except Exception:
        return False


def _step_signature(ordered: list[dict]) -> str:
    """Order-independent fingerprint of a step's tool calls (name + raw args).

    Two steps with the same signature mean the model is asking for the exact
    same action again — the core signal we use to detect a stuck/looping agent.
    """
    items = sorted(
        f"{(c.get('name') or '').strip()}\x00{(c.get('args') or '').strip()}"
        for c in ordered
    )
    return hashlib.sha256("\x01".join(items).encode("utf-8", "ignore")).hexdigest()


async def _model_turn(client, send, tools, temperature, tag, *, thinking=True, max_retries=3):
    """Resiliently stream ONE model turn.

    Yields event strings for the live UI as deltas arrive, then finishes with a
    final tuple:
      ("__result__", text_buf:list, tool_calls:dict)   — usable turn
      ("__error__", message:str)                        — gave up after retries

    A stream that dies *before* producing anything usable is retried cleanly (no
    duplicated output). A stream that dies *after* producing usable content/tool
    calls finishes with what arrived — so the agent keeps going instead of
    surfacing "Stream interrupted".
    """
    for attempt in range(max_retries):
        text_buf: list[str] = []
        tool_calls: dict = {}
        emitted = False
        try:
            async for chunk in client.stream_guarded(send, tools=tools,
                                                     temperature=temperature, thinking=thinking):
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                reasoning = extract_reasoning(delta)
                if reasoning:
                    emitted = True
                    yield _ev({"type": "reasoning", "delta": reasoning, **tag})

                if delta.content:
                    text_buf.append(delta.content)
                    emitted = True
                    yield _ev({"type": "content", "delta": delta.content, **tag})

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        slot = tool_calls.setdefault(tc.index, {"id": None, "name": "", "args": ""})
                        if tc.id:
                            slot["id"] = tc.id
                        if tc.function and tc.function.name:
                            slot["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            slot["args"] += tc.function.arguments

            yield ("__result__", text_buf, tool_calls)
            return
        except Exception as e:
            have_text = bool("".join(text_buf).strip())
            have_tools = bool(tool_calls)
            tools_ok = have_tools and all(_args_complete(c["args"]) for c in tool_calls.values())

            # Nothing usable yet → retry the whole turn cleanly.
            if not emitted and not have_tools and attempt < max_retries - 1:
                await asyncio.sleep(min(1.5 * (attempt + 1), 4))
                continue
            # Complete tool calls (or solid text with no partial tool args) → use them.
            if tools_ok or (have_text and not have_tools):
                yield ("__result__", text_buf, tool_calls if tools_ok else {})
                return
            # Partial/garbled output → one more clean retry if we can.
            if attempt < max_retries - 1:
                await asyncio.sleep(min(1.5 * (attempt + 1), 4))
                continue
            yield ("__error__", str(e) or "the model connection dropped")
            return


async def agentic_loop(client, pool, convo, tools, temperature, max_steps,
                       permission_mode, *, agent_id=None, allow_all_override=False):
    """Reusable plan->act->observe loop. Shared by the agentic path and swarm
    builder workers. Tag events with ``agent_id`` for swarm worker attribution."""
    allow_all = allow_all_override or (permission_mode or "ask") != "ask"
    tag = {"agent": agent_id} if agent_id else {}
    last_summary_len = len(convo)

    # No-progress guard: count how often the model asks for the exact same step
    # (same tool calls, or the same large answer). Repeats mean it's stuck in a
    # loop instead of finishing — we nudge it, then stop cleanly.
    tool_seen: dict[str, int] = {}
    content_seen: dict[str, int] = {}
    nudges_used = 0

    for step in range(1, max_steps + 1):
        if not agent_id:
            yield _status_ev(pool)

        # Context hygiene: summarize when the thread grows long; always prune
        # bulky old tool output before sending.
        if len(convo) - last_summary_len >= 12:
            summarized = await summarize_history(convo, client)
            if summarized:
                convo = summarized
                last_summary_len = len(convo)
        send = prune_context(convo)

        text_buf = []
        tool_calls = {}
        step_error = None

        async for item in _model_turn(client, send, tools, temperature, tag):
            if isinstance(item, str):
                yield item                       # live reasoning/content delta
            elif item[0] == "__result__":
                text_buf, tool_calls = item[1], item[2]
            elif item[0] == "__error__":
                step_error = item[1]

        if step_error is not None:
            yield _ev({"type": "error",
                       "error": f"The model connection dropped before finishing ({step_error}). "
                                f"Please send the message again.", **tag})
            return

        if not tool_calls:
            if not "".join(text_buf).strip() and not agent_id:
                yield _ev({"type": "content",
                           "delta": "I finished without producing a visible answer. "
                                    "Could you rephrase or add a bit more detail?"})
            yield _ev({"type": "done", **tag})
            return

        ordered = [tool_calls[i] for i in sorted(tool_calls.keys())]

        # ---- No-progress / loop guard --------------------------------------
        # Checked BEFORE we commit the assistant turn, so a skipped repeat never
        # leaves a dangling tool_calls message in the conversation.
        tsig = _step_signature(ordered)
        tool_seen[tsig] = tool_seen.get(tsig, 0) + 1
        reps = tool_seen[tsig]
        ctext = "".join(text_buf).strip()
        if len(ctext) >= 200:
            csig = hashlib.sha256(ctext.encode("utf-8", "ignore")).hexdigest()
            content_seen[csig] = content_seen.get(csig, 0) + 1
            reps = max(reps, content_seen[csig])

        if reps >= 3:
            yield _ev({"type": "content",
                       "delta": "\n\n_(Stopped: I was repeating the same step without making "
                                "new progress. The result above is final — ask me to continue "
                                "if you need more.)_", **tag})
            yield _ev({"type": "done", **tag})
            return
        if reps >= 2 and nudges_used < 2:
            nudges_used += 1
            convo.append({"role": "system", "content":
                "You just repeated an action you already completed — the same tool call with "
                "the same arguments, or the same answer you already gave. You ALREADY have "
                "that result above. Do not repeat it. If the task is now complete, reply with "
                "your final summary and NO tool calls. Only call a tool if it does something "
                "genuinely new."})
            continue

        convo.append({
            "role": "assistant",
            "content": "".join(text_buf),
            "tool_calls": [
                {"id": c["id"] or f"call_{step}_{i}", "type": "function",
                 "function": {"name": _clean_tool_name(c["name"]), "arguments": c["args"] or "{}"}}
                for i, c in enumerate(ordered)
            ],
        })

        # Normalize each call.
        calls = []
        for i, c in enumerate(ordered):
            call_id = c["id"] or f"call_{step}_{i}"
            name = _clean_tool_name(c["name"])
            try:
                args = json.loads(c["args"]) if c["args"].strip() else {}
            except Exception:
                args = {}
            meta = TOOL_META.get(name, {"label": name, "icon": "wrench", "kind": "read"})
            calls.append({"call_id": call_id, "name": name, "args": args, "meta": meta})

        results_by_id: dict[str, str] = {}

        # ---- Phase 1: parallel read-only tool calls ------------------------
        parallel = [c for c in calls if is_parallel_safe(c["name"])]
        if parallel:
            for c in parallel:
                yield _ev({"type": "tool_start", "id": c["call_id"], "name": c["name"],
                           "label": c["meta"]["label"], "icon": c["meta"]["icon"],
                           "kind": c["meta"]["kind"], "args": c["args"], **tag})
            results = await asyncio.gather(
                *[asyncio.to_thread(execute_tool, c["name"], c["args"]) for c in parallel]
            )
            for c, result in zip(parallel, results):
                ok = not str(result).lower().startswith(("error", "blocked", "unknown tool"))
                results_by_id[c["call_id"]] = str(result)
                yield _ev({"type": "tool_result", "id": c["call_id"], "ok": ok,
                           "result": str(result)[:12000], **tag})

        # ---- Phase 2: risky / mutating tool calls (sequential, gated) ------
        for c in calls:
            if is_parallel_safe(c["name"]):
                continue
            call_id, name, args, meta = c["call_id"], c["name"], c["args"], c["meta"]

            if not allow_all and meta["kind"] in RISKY_KINDS:
                rid = permissions.create_request()
                yield _ev({"type": "permission_request", "id": rid, "call_id": call_id,
                           "name": name, "label": meta["label"], "icon": meta["icon"],
                           "kind": meta["kind"], "args": args, **tag})
                decision = "deny"
                waited = 0.0
                while waited < 900:
                    if permissions.is_set(rid):
                        decision = permissions.get_decision(rid) or "deny"
                        break
                    await asyncio.sleep(0.4)
                    waited += 0.4
                    if int(waited * 10) % 40 == 0:
                        yield _ev({"type": "heartbeat"})
                permissions.clear(rid)

                if decision == "allow_all":
                    allow_all = True
                elif decision == "deny":
                    yield _ev({"type": "tool_start", "id": call_id, "name": name,
                               "label": meta["label"], "icon": meta["icon"],
                               "kind": meta["kind"], "args": args, **tag})
                    yield _ev({"type": "tool_result", "id": call_id, "ok": False,
                               "result": "Denied by user.", **tag})
                    results_by_id[call_id] = ("The user denied permission for this action. "
                                              "Do not retry it; try a different approach or ask "
                                              "the user how to proceed.")
                    continue

            yield _ev({"type": "tool_start", "id": call_id, "name": name,
                       "label": meta["label"], "icon": meta["icon"],
                       "kind": meta["kind"], "args": args, **tag})

            # Live-streaming tools (shell / python) push stdout/stderr as it runs.
            if name in STREAMING_DISPATCH:
                loop = asyncio.get_running_loop()
                q: asyncio.Queue = asyncio.Queue()

                def _on_line(text, _q=q, _loop=loop):
                    try:
                        _loop.call_soon_threadsafe(_q.put_nowait, text)
                    except RuntimeError:
                        pass

                task = asyncio.create_task(
                    asyncio.to_thread(execute_tool_streaming, name, args, _on_line))
                while not (task.done() and q.empty()):
                    try:
                        text = await asyncio.wait_for(q.get(), timeout=0.2)
                    except asyncio.TimeoutError:
                        continue
                    yield _ev({"type": "tool_stream", "id": call_id, "delta": text, **tag})
                result = await task
            else:
                result = await asyncio.to_thread(execute_tool, name, args)

            ok = not str(result).lower().startswith(("error", "blocked", "unknown tool"))
            results_by_id[call_id] = str(result)
            yield _ev({"type": "tool_result", "id": call_id, "ok": ok,
                       "result": str(result)[:12000], **tag})

        # Append tool results back into the conversation in the original order.
        for c in calls:
            convo.append({"role": "tool", "tool_call_id": c["call_id"],
                          "content": str(results_by_id.get(c["call_id"], ""))[:16000]})

    yield _ev({"type": "content",
               "delta": f"\n\n_(Reached the {max_steps}-step limit. Ask me to continue if needed.)_",
               **tag})
    yield _ev({"type": "done", **tag})


async def _run_simple(client, pool, messages, temperature, model_name):
    """One fast streaming reply, no tools, served from the semantic cache when a
    near-identical question was answered before. Yields events, or the string
    "__ESCALATE__" if the model signals it needs the full toolkit."""
    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    question = (last_user.get("content") if last_user else "") or ""

    # Time-sensitive questions must never be served stale from cache.
    ql = question.lower()
    time_sensitive = any(w in ql for w in (
        "date", "time", "today", "tonight", "now", "current", "latest", "news",
        "weather", "price", "stock", "score", "this year", "right now",
    ))

    # ---- Semantic cache: zero-API answer for repeat/equivalent questions ----
    hit = None if time_sensitive else cache.lookup(question, model_name)
    if hit:
        yield _ev({"type": "cache_hit", "similarity": hit["similarity"]})
        # Re-stream the cached answer in small chunks for a natural feel.
        ans = hit["answer"]
        for i in range(0, len(ans), 24):
            yield _ev({"type": "content", "delta": ans[i:i + 24]})
            await asyncio.sleep(0)
        yield _ev({"type": "done"})
        return

    convo = [{"role": "system", "content": _env_preamble() + router.SIMPLE_SYSTEM}]
    convo.extend(messages)

    yield _status_ev(pool)

    sentinel = router.NEEDS_TOOLS_SENTINEL
    decided = False
    emitted_any = False
    answer_buf = []

    # Resilient: a dropped connection retries cleanly while nothing has been
    # shown yet; if it drops after we've started answering, finish with what we
    # have. Never surface "Stream interrupted".
    for attempt in range(3):
        head = ""
        try:
            async for chunk in client.stream_guarded(convo, tools=None,
                                                     temperature=min(temperature, 0.5),
                                                     thinking=False):
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if not delta.content:
                    continue

                if decided:
                    answer_buf.append(delta.content)
                    yield _ev({"type": "content", "delta": delta.content})
                    emitted_any = True
                    continue

                head += delta.content
                stripped = head.lstrip()
                if sentinel.startswith(stripped) and len(stripped) < len(sentinel):
                    continue
                if stripped.startswith(sentinel):
                    yield "__ESCALATE__"
                    return

                decided = True
                answer_buf.append(head)
                yield _ev({"type": "content", "delta": head})
                emitted_any = True
            break  # stream finished cleanly
        except Exception:
            if not emitted_any and attempt < 2:
                await asyncio.sleep(1.0 * (attempt + 1))
                continue          # clean retry — nothing shown yet
            if emitted_any:
                break             # finish gracefully with what we have
            yield "__ESCALATE__"  # let the full agent try instead of erroring
            return

    if not decided and head.strip() and not head.strip().startswith(sentinel):
        answer_buf.append(head)
        yield _ev({"type": "content", "delta": head})
        emitted_any = True

    if not emitted_any and not decided:
        yield "__ESCALATE__"
        return

    # Cache the fresh answer for next time (best-effort; never cache time-sensitive).
    if not time_sensitive:
        cache.store(question, "".join(answer_buf), model_name)
    yield _ev({"type": "done"})
