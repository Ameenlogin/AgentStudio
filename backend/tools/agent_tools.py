"""Meta-tools that let the agent manage its own process — structured todos,
ruthless verification, goal tracking and project-instruction scanning.

These are thin wrappers around the services so the loop in agents/agent.py can
also read their state to drive the live NDJSON event stream (todo_update /
goal_progress / verification_result).
"""
from services import todo_manager
from services.verification import verify_work as _verify_work
from services import project_memory


def todo_write(todos) -> str:
    """Create or update the live checklist. Merges by id; returns the rendered list."""
    if not isinstance(todos, list):
        return ("Error: todo_write expects a 'todos' array of "
                "{id, content, status} objects.")
    return todo_manager.write(todos)


def verify_work(command: str = "", framework: str = "") -> str:
    """Run tests / build / compile and return a structured PASSED / FAILED verdict."""
    return _verify_work(command, framework)


def update_goal(goal: str = "", progress: str = "", percent=None) -> str:
    """Record the high-level goal + progress (surfaced as a goal_progress event)."""
    goal = (goal or "").strip()
    progress = (progress or "").strip()
    bits = []
    if goal:
        bits.append(f"Goal: {goal}")
    if percent is not None:
        try:
            bits.append(f"{int(percent)}% complete")
        except Exception:
            pass
    if progress:
        bits.append(progress)
    return "Goal updated. " + (" · ".join(bits) if bits else "(no detail given)")


def scan_project_instructions() -> str:
    """Force a re-scan of AGENTS.md / CLAUDE.md / .cursorrules etc. in the workspace."""
    return project_memory.tool_scan()
