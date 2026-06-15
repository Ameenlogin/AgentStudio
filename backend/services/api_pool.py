"""Smart API key pool with sliding-window rate tracking, health-aware key
rotation and multi-endpoint (region) routing.

Core guarantee: each key is held to a safety cap (SAFE_RPM = 36) via a 60s
sliding window — deliberately under NVIDIA's 40 RPM/key limit so a key never
reaches 40/40 in a minute and we never trip a 429, even on long agentic tasks
that make many calls. On top of that:

  • Health-aware rotation — `acquire()` hands out the *healthiest* key with the
    most head-room instead of a blind round-robin, and steers away from any key
    that recently 429'd or errored until its cooldown expires.
  • Endpoint routing — requests target the lowest-latency healthy NIM endpoint.
    Extra regional endpoints can be supplied via the KIMI_EXTRA_ENDPOINTS env
    var (comma-separated). With none set it behaves exactly like before: a
    single integrate.api.nvidia.com endpoint.
"""
import os
import time
import asyncio
from collections import deque
from dataclasses import dataclass, field
from openai import AsyncOpenAI

# Safety cap per key: stay comfortably below NVIDIA's 40 RPM/key hard limit so a
# key never reaches 40/40 in any 60s window (no 429s, even on long tool loops).
SAFE_RPM = 36


# ── Endpoint (region) health ──────────────────────────────────────────────────
@dataclass
class Endpoint:
    base_url: str
    ewma_latency: float = 0.4          # seconds, exponentially-weighted moving avg
    consecutive_failures: int = 0
    cooldown_until: float = 0.0

    @property
    def healthy(self) -> bool:
        return time.monotonic() >= self.cooldown_until

    def record_latency(self, dt: float) -> None:
        # EWMA so a one-off slow call doesn't permanently demote a region.
        self.ewma_latency = 0.7 * self.ewma_latency + 0.3 * dt
        self.consecutive_failures = 0

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        # Back off this region for a few seconds, growing with repeated failures.
        self.cooldown_until = time.monotonic() + min(30.0, 3.0 * self.consecutive_failures)


class EndpointRouter:
    """Picks the lowest-latency healthy endpoint; falls back to the first one."""

    def __init__(self, base_url: str):
        urls = [base_url]
        extra = os.environ.get("KIMI_EXTRA_ENDPOINTS", "").strip()
        if extra:
            for u in extra.split(","):
                u = u.strip()
                if u and u not in urls:
                    urls.append(u)
        self.endpoints = [Endpoint(u) for u in urls]

    def best(self) -> Endpoint:
        healthy = [e for e in self.endpoints if e.healthy]
        pool = healthy or self.endpoints
        return min(pool, key=lambda e: e.ewma_latency)

    def status(self) -> list[dict]:
        return [
            {
                "base_url": e.base_url,
                "latency_ms": round(e.ewma_latency * 1000),
                "healthy": e.healthy,
                "failures": e.consecutive_failures,
            }
            for e in self.endpoints
        ]


# ── Per-key slot ──────────────────────────────────────────────────────────────
@dataclass
class AgentSlot:
    """One API key slot with its own rate tracker and health state."""
    key: str
    router: EndpointRouter
    rpm_limit: int = SAFE_RPM  # safety cap under NVIDIA's 40 RPM/key; window self-throttles
    _clients: dict = field(default_factory=dict)
    _timestamps: deque = field(default_factory=deque)
    _deprioritized_until: float = 0.0
    consecutive_errors: int = 0
    total_errors: int = 0

    def client_for(self, base_url: str) -> AsyncOpenAI:
        c = self._clients.get(base_url)
        if c is None:
            c = AsyncOpenAI(api_key=self.key, base_url=base_url)
            self._clients[base_url] = c
        return c

    @property
    def client(self) -> AsyncOpenAI:
        """Client bound to the currently-best endpoint (back-compat accessor)."""
        return self.client_for(self.router.best().base_url)

    @property
    def rpm_used(self) -> int:
        now = time.monotonic()
        while self._timestamps and self._timestamps[0] < now - 60:
            self._timestamps.popleft()
        return len(self._timestamps)

    @property
    def healthy(self) -> bool:
        return time.monotonic() >= self._deprioritized_until

    @property
    def available(self) -> bool:
        return self.rpm_used < self.rpm_limit and self.healthy

    @property
    def headroom(self) -> int:
        return max(0, self.rpm_limit - self.rpm_used)

    def record_request(self):
        self._timestamps.append(time.monotonic())

    def record_success(self):
        self.consecutive_errors = 0

    def record_error(self):
        self.consecutive_errors += 1
        self.total_errors += 1
        # Brief, escalating cooldown so a flaky key is rotated out automatically.
        self.deprioritize(min(30.0, 5.0 * self.consecutive_errors))

    def deprioritize(self, seconds: float = 10.0):
        self._deprioritized_until = max(self._deprioritized_until, time.monotonic() + seconds)

    def seconds_until_free(self) -> float:
        if self.available:
            return 0.0
        waits = []
        if not self.healthy:
            waits.append(self._deprioritized_until - time.monotonic())
        if self.rpm_used >= self.rpm_limit and self._timestamps:
            waits.append((self._timestamps[0] + 60.0) - time.monotonic())
        return max(0.0, min(waits)) if waits else 0.0


class APIPool:
    """Pool across N API keys with health-aware rotation + endpoint routing."""

    def __init__(self, keys: list[str], base_url: str, rpm_per_key: int = SAFE_RPM):
        self.router = EndpointRouter(base_url)
        self.slots = [
            AgentSlot(key=k, router=self.router, rpm_limit=rpm_per_key)
            for k in keys if k and k.strip()
        ]
        if not self.slots:
            raise ValueError("At least one API key is required.")
        self._idx = 0  # round-robin tiebreaker pointer

    @property
    def total_rpm_used(self) -> int:
        return sum(s.rpm_used for s in self.slots)

    @property
    def total_rpm_limit(self) -> int:
        return sum(s.rpm_limit for s in self.slots)

    def status(self) -> list[dict]:
        return [
            {
                "id": i + 1,
                "rpm_used": s.rpm_used,
                "rpm_limit": s.rpm_limit,
                "status": "deprioritized" if not s.healthy
                          else "active" if s.rpm_used > 0 else "idle",
                "headroom": s.headroom,
                "errors": s.total_errors,
            }
            for i, s in enumerate(self.slots)
        ]

    async def acquire(self) -> AgentSlot:
        """Get the healthiest available slot (most head-room). Waits if all are
        momentarily at capacity, then force-uses the least-loaded one."""
        max_wait = 120  # seconds
        waited = 0.0

        while waited < max_wait:
            available = [s for s in self.slots if s.available]
            if available:
                # Prefer the most head-room; round-robin among equals for fairness.
                top = max(s.headroom for s in available)
                tied = [s for s in available if s.headroom == top]
                slot = tied[self._idx % len(tied)]
                self._idx += 1
                slot.record_request()
                return slot

            min_wait = min(s.seconds_until_free() for s in self.slots)
            sleep_time = max(0.5, min(min_wait + 0.1, 5.0))
            await asyncio.sleep(sleep_time)
            waited += sleep_time

        best = min(self.slots, key=lambda s: s.rpm_used)
        best.record_request()
        return best

    def handle_rate_limit(self, slot: AgentSlot):
        """Called on a 429 — back the key off so the pool rotates to another."""
        slot.deprioritize(15.0)
        slot.record_error()
