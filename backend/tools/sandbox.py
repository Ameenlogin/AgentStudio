"""Workspace sandbox: every tool path is resolved inside one root folder so the
agent can't wander across the whole machine.

The root is a ``ContextVar`` rather than a plain module global, so each request
(each asyncio task, and the worker threads it spawns via ``asyncio.to_thread``)
gets its *own* workspace. That keeps concurrent users isolated — user A's chat
can't read or clobber user B's files — and is what makes the hosted, multi-user
deployment safe. In the single-user desktop app it behaves exactly as before."""
import os
import re
import contextvars

_DEFAULT_ROOT = os.path.abspath("./workspace")

# Per-context current workspace. Defaults to ./workspace when nothing set it
# (e.g. a tool invoked outside a request, or the classic desktop install).
_workspace_root: contextvars.ContextVar[str] = contextvars.ContextVar(
    "workspace_root", default=_DEFAULT_ROOT
)


def set_workspace(path: str) -> str:
    """Point the *current context's* workspace at ``path`` (created if needed)."""
    root = os.path.abspath(os.path.expanduser(path)) if path else _workspace_root.get()
    _workspace_root.set(root)
    os.makedirs(root, exist_ok=True)
    return root


def get_workspace() -> str:
    root = _workspace_root.get()
    os.makedirs(root, exist_ok=True)
    return root


def _workspaces_base() -> str:
    """Root that holds every per-user workspace. A path on the persistent volume
    in the hosted deployment (``AGENT_STUDIO_WORKSPACES``), else ``./workspaces``."""
    return os.environ.get("AGENT_STUDIO_WORKSPACES") or os.path.abspath("./workspaces")


def workspace_for_user(user_id) -> str:
    """Map a *logged-in* site account to its own private, persistent workspace.

    This is the authoritative isolation key on the hosted site: the user's id
    comes from the signed session cookie (server-side), so two accounts can never
    land in the same folder — each one has its own files and 'computer' memory.
    """
    return os.path.join(_workspaces_base(), f"u{int(user_id)}")


def workspace_for_client(client_id: str | None) -> str | None:
    """Map a browser's anonymous client id to its own private workspace dir.

    Returns ``None`` when there is no client id (the desktop app), so callers
    fall back to the configured single-user workspace. Kept for the keyless
    desktop/legacy path; the hosted site keys off the account via
    ``workspace_for_user`` instead."""
    cid = re.sub(r"[^A-Za-z0-9_-]", "", (client_id or ""))[:64]
    if not cid:
        return None
    return os.path.join(_workspaces_base(), cid)


def resolve(path: str) -> str:
    """Resolve a (possibly relative) path against the workspace, blocking escapes.

    Uses ``realpath`` on both the root and the candidate so a symlink inside the
    workspace can't be used to read or write outside it (the candidate's existing
    parents are resolved even when the leaf file doesn't exist yet)."""
    if not path:
        path = "."
    ws = get_workspace()
    root = os.path.realpath(ws)
    candidate = os.path.realpath(os.path.join(ws, os.path.expanduser(path)))
    if candidate != root and not candidate.startswith(root + os.sep):
        raise PermissionError(
            f"Path '{path}' is outside the workspace. All paths must stay inside {root}."
        )
    return candidate


def rel(path: str) -> str:
    """Display a path relative to the workspace root."""
    try:
        return os.path.relpath(path, _workspace_root.get())
    except ValueError:
        return path
