"""Workspace sandbox: every tool path is resolved inside one root folder so the
agent can't wander across the whole machine. The root is configurable in Settings."""
import os

_workspace_root = os.path.abspath("./workspace")


def set_workspace(path: str) -> str:
    global _workspace_root
    if path:
        _workspace_root = os.path.abspath(os.path.expanduser(path))
    os.makedirs(_workspace_root, exist_ok=True)
    return _workspace_root


def get_workspace() -> str:
    os.makedirs(_workspace_root, exist_ok=True)
    return _workspace_root


def resolve(path: str) -> str:
    """Resolve a (possibly relative) path against the workspace, blocking escapes.

    Uses ``realpath`` on both the root and the candidate so a symlink inside the
    workspace can't be used to read or write outside it (the candidate's existing
    parents are resolved even when the leaf file doesn't exist yet)."""
    if not path:
        path = "."
    root = os.path.realpath(_workspace_root)
    candidate = os.path.realpath(os.path.join(_workspace_root, os.path.expanduser(path)))
    if candidate != root and not candidate.startswith(root + os.sep):
        raise PermissionError(
            f"Path '{path}' is outside the workspace. All paths must stay inside {root}."
        )
    return candidate


def rel(path: str) -> str:
    """Display a path relative to the workspace root."""
    try:
        return os.path.relpath(path, _workspace_root)
    except ValueError:
        return path
