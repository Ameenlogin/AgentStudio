"""Conversation context pruning + auto-summarization.

Long agentic conversations balloon with verbose tool outputs and many turns,
which slows every subsequent request and wastes tokens. Two strategies:

  • prune_context() — cheap, always-on. Truncates bulky old tool results and
    keeps recent turns verbatim. No API call.
  • summarize_history() — when a conversation crosses a turn threshold, fold the
    older turns into a single compact summary note via one pooled model call,
    so context stays small without losing the thread.

Both preserve the system prompt and the most recent turns untouched.
"""
from __future__ import annotations

SUMMARY_TURN_THRESHOLD = 20   # messages (excl. system) before we summarize
KEEP_RECENT = 8               # most-recent messages always kept verbatim
TOOL_RESULT_CAP = 1500        # chars to keep from an *old* tool result


def _msg_text(m: dict) -> str:
    c = m.get("content")
    return c if isinstance(c, str) else ""


def prune_context(convo: list[dict]) -> list[dict]:
    """Truncate large tool results in the older part of the conversation."""
    if len(convo) <= KEEP_RECENT + 1:
        return convo
    cutoff = len(convo) - KEEP_RECENT
    out = []
    for i, m in enumerate(convo):
        if i < cutoff and m.get("role") == "tool":
            text = _msg_text(m)
            if len(text) > TOOL_RESULT_CAP:
                m = dict(m)
                m["content"] = text[:TOOL_RESULT_CAP] + "\n[…older tool output truncated for context]"
        out.append(m)
    return out


async def summarize_history(convo: list[dict], client) -> list[dict] | None:
    """If the conversation is long, compress everything except the system prompt
    and the most recent turns into a single summary note. Returns the new convo,
    or None if no summarization was needed."""
    system = [m for m in convo if m.get("role") == "system"]
    body = [m for m in convo if m.get("role") != "system"]
    if len(body) < SUMMARY_TURN_THRESHOLD:
        return None

    # Choose a cut that lands on a clean user-turn boundary, so we never split an
    # assistant(tool_calls) message from its tool results — the API rejects an
    # orphaned tool message or a dangling tool_calls with no responses.
    cut = len(body) - KEEP_RECENT
    while cut < len(body) and body[cut].get("role") != "user":
        cut += 1
    if cut >= len(body):
        return None

    head = body[:cut]
    tail = body[cut:]
    if not head:
        return None

    transcript = []
    for m in head:
        role = m.get("role", "?")
        text = _msg_text(m)
        if m.get("tool_calls"):
            names = ", ".join(tc["function"]["name"] for tc in m["tool_calls"])
            text = (text + f" [called tools: {names}]").strip()
        transcript.append(f"{role.upper()}: {text[:1200]}")
    joined = "\n".join(transcript)[:12000]

    prompt = [
        {"role": "system", "content":
            "Summarize the following conversation so far into a tight briefing "
            "that another instance of the agent can use to continue seamlessly. "
            "Capture: the user's goal, decisions made, files/commands created or "
            "changed, key findings, and any open threads. Be specific and concise."},
        {"role": "user", "content": joined},
    ]

    try:
        summary_parts: list[str] = []
        async for chunk in client.stream_guarded(prompt, tools=None, temperature=0.3, thinking=False):
            if chunk.choices and chunk.choices[0].delta.content:
                summary_parts.append(chunk.choices[0].delta.content)
        summary = "".join(summary_parts).strip()
    except Exception:
        return None

    if not summary:
        return None

    note = {"role": "system",
            "content": "[Summary of earlier conversation]\n" + summary}
    return system + [note] + tail
