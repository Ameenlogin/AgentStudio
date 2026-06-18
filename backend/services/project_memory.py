"""ProjectMemory / InstructionScanner — make the agent aware of project-specific
instruction files (AGENTS.md, CLAUDE.md, .cursorrules, …) the way Grok/Cursor do.

On the first turn of a run the agent scans the workspace for these files and the
relevant content is injected into the system prompt as a [PROJECT INSTRUCTIONS]
block, so the agent respects house rules without being told. A
``scan_project_instructions`` tool lets it force a re-scan mid-task.
"""
import os
from tools.sandbox import get_workspace

# Highest-signal first. These are conventions across Claude Code, Cursor, Grok,
# Windsurf, Aider and the OpenAI agents ecosystem.
INSTRUCTION_FILES = [
    "AGENTS.md", "CLAUDE.md", "AGENT.md", "CLAUDE.local.md",
    ".cursorrules", ".clauderules", ".windsurfrules", ".aider.conf.yml",
    "GEMINI.md", "CONVENTIONS.md", "CONTRIBUTING.md",
]
# Searched in the workspace root plus these common locations.
SEARCH_SUBDIRS = ["", "docs", ".github", ".cursor"]


def _candidates(ws: str):
    seen = set()
    for sub in SEARCH_SUBDIRS:
        base = os.path.join(ws, sub) if sub else ws
        for name in INSTRUCTION_FILES:
            p = os.path.join(base, name)
            rp = os.path.realpath(p)
            if rp in seen:
                continue
            seen.add(rp)
            if os.path.isfile(p):
                yield p


def scan(max_chars: int = 6000) -> str:
    """Return a [PROJECT INSTRUCTIONS] block for injection, or '' if none found."""
    ws = get_workspace()
    found: list[tuple[str, str]] = []
    for p in _candidates(ws):
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read().strip()
        except Exception:
            continue
        if text:
            found.append((os.path.relpath(p, ws), text))
    if not found:
        return ""

    parts = []
    budget = max_chars
    for rel, text in found:
        if budget <= 0:
            break
        chunk = text[:budget]
        if len(text) > len(chunk):
            chunk += "\n…(truncated)"
        parts.append(f"### {rel}\n{chunk}")
        budget -= len(chunk)
    return (
        "[PROJECT INSTRUCTIONS] Instruction files found in this workspace. Treat "
        "them as authoritative house rules for this project and follow them unless "
        "the user overrides them:\n\n" + "\n\n".join(parts)
    )


def tool_scan() -> str:
    """The scan_project_instructions tool result (human-readable)."""
    block = scan()
    if not block:
        return ("No project instruction files (AGENTS.md, CLAUDE.md, .cursorrules, …) "
                "found in the workspace.")
    return block
