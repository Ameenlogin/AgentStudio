"""Git tools for the agent, sandboxed to the workspace."""
import subprocess
from tools.sandbox import get_workspace

TIMEOUT = 30

def _git(args: str) -> str:
    try:
        proc = subprocess.run(
            f"git {args}", shell=True, cwd=get_workspace(),
            capture_output=True, text=True, timeout=TIMEOUT,
        )
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        if proc.returncode != 0 and err:
            return f"Error (exit {proc.returncode}): {err[:4000]}"
        return out[:8000] or "[no output]"
    except subprocess.TimeoutExpired:
        return f"Error: git command timed out after {TIMEOUT}s"
    except Exception as e:
        return f"Error running git: {e}"

def git_status() -> str:
    return _git("status --short")

def git_diff(path: str = "") -> str:
    cmd = f"diff {path}" if path else "diff"
    return _git(cmd)

def git_log(n: int = 10) -> str:
    return _git(f"log --oneline -n {n}")

def git_commit(message: str) -> str:
    _git("add -A")
    return _git(f'commit -m "{message}"')
