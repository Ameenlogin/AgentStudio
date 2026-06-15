"""In-memory permission registry for Claude-Code-style approval prompts.

The agent loop can pause before a risky tool, emit a `permission_request`
event, and await the user's decision. A separate HTTP endpoint
(`/api/permissions/resolve`) records the decision, which unblocks the loop.

Decisions: "allow" (run once), "allow_all" (run this + all later actions this
run), "deny" (skip the action).
"""
import asyncio
import uuid

_pending: dict[str, dict] = {}


def create_request() -> str:
    rid = uuid.uuid4().hex[:12]
    _pending[rid] = {"event": asyncio.Event(), "decision": None}
    return rid


def resolve(rid: str, decision: str) -> bool:
    slot = _pending.get(rid)
    if not slot:
        return False
    slot["decision"] = decision
    slot["event"].set()
    return True


def is_set(rid: str) -> bool:
    slot = _pending.get(rid)
    return bool(slot and slot["event"].is_set())


def get_decision(rid: str) -> str | None:
    slot = _pending.get(rid)
    return slot["decision"] if slot else None


def clear(rid: str) -> None:
    _pending.pop(rid, None)
