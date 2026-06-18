"""Live, per-run structured task checklist (the single biggest reliability
multiplier for ambitious, multi-step work).

The agent maintains a visible to-do list with the ``todo_write`` tool. State is
kept per agentic run, keyed by a contextvar the loop sets at the top of each run,
so concurrent chats and swarm workers never clobber each other's lists. The
stateless tool layer (``tools/tool_router.py``) reaches the right list through
``current_run``; ``agents/agent.py`` reads the list back to inject it into every
turn and to emit ``todo_update`` events for the timeline UI.
"""
import contextvars

# Set by agentic_loop for each run. The default keeps direct unit-testing simple.
current_run: contextvars.ContextVar = contextvars.ContextVar("todo_run", default="__default__")

_STORE: dict[str, list[dict]] = {}
_VALID = {"pending", "in_progress", "completed", "cancelled"}
_MARK = {"completed": "[x]", "in_progress": "[~]", "cancelled": "[-]", "pending": "[ ]"}


def _rid(run_id=None) -> str:
    return run_id or current_run.get()


def _list(run_id=None) -> list[dict]:
    return _STORE.setdefault(_rid(run_id), [])


def reset(run_id=None) -> None:
    """Start a fresh checklist for a run (called once when the loop begins)."""
    _STORE[_rid(run_id)] = []


def discard(run_id=None) -> None:
    _STORE.pop(_rid(run_id), None)


def write(todos, run_id=None) -> str:
    """Merge an incoming todo list by id: update existing items in place, append
    new ones, keep order stable. Returns the rendered checklist for the model."""
    items = _list(run_id)
    by_id = {t["id"]: t for t in items}
    order = [t["id"] for t in items]
    for raw in todos or []:
        if not isinstance(raw, dict):
            continue
        content = str(raw.get("content") or raw.get("task") or raw.get("title") or "").strip()
        tid = (str(raw.get("id") or content)[:160]).strip()
        if not tid:
            continue
        status = str(raw.get("status") or "pending").strip().lower()
        if status not in _VALID:
            status = "pending"
        if tid in by_id:
            if content:
                by_id[tid]["content"] = content
            by_id[tid]["status"] = status
        else:
            entry = {"id": tid, "content": content or tid, "status": status}
            by_id[tid] = entry
            order.append(tid)
    _STORE[_rid(run_id)] = [by_id[i] for i in order]
    return render(run_id)


def get(run_id=None) -> list[dict]:
    """The current todos as a plain list (for the todo_update event)."""
    return [dict(t) for t in _list(run_id)]


def render(run_id=None) -> str:
    items = _list(run_id)
    if not items:
        return "Todo list is empty."
    done = sum(1 for t in items if t["status"] == "completed")
    lines = [f"{_MARK.get(t['status'], '[ ]')} {t['content']}" for t in items]
    return f"Todos ({done}/{len(items)} done):\n" + "\n".join(lines)


def active_block(run_id=None) -> str:
    """A compact reminder injected into the model's context each turn, or '' when
    there are no todos so simple tasks stay clutter-free."""
    items = _list(run_id)
    if not items:
        return ""
    return (
        "[ACTIVE TODOS] Your live checklist for this task — keep it current with "
        "todo_write (mark items in_progress as you start them and completed the "
        "moment they're done). Do not stop while any item is still pending or "
        "in_progress.\n" + render(run_id)
    )
