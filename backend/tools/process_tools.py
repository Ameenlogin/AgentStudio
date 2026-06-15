"""Background process management.

Long-lived commands (dev servers, watchers, `npm run dev`) would block the agent
loop and time out under run_command. start_process launches them detached in the
workspace, captures their output into a ring buffer, and hands back a handle the
agent can read or stop. This is what makes "build it AND run it, then test it"
actually work: start the server, read its logs, then hit it with http_request.
"""
import os
import time
import signal
import threading
import subprocess
import itertools
from collections import deque
from tools.sandbox import get_workspace

_PROCS: dict[str, dict] = {}
_counter = itertools.count(1)
_lock = threading.Lock()
_MAX_LINES = 800


def _pump(pid: str, pipe) -> None:
    info = _PROCS.get(pid)
    if not info:
        return
    buf = info["output"]
    try:
        for line in iter(pipe.readline, ""):
            if not line:
                break
            buf.append(line.rstrip("\n"))
    except Exception:
        pass
    finally:
        try:
            pipe.close()
        except Exception:
            pass


def start_process(command: str) -> str:
    """Launch a long-running command in the background and return a handle."""
    cmd = (command or "").strip()
    if not cmd:
        return "Error: empty command."
    ws = get_workspace()
    try:
        proc = subprocess.Popen(
            cmd, shell=True, cwd=ws,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, start_new_session=True,  # own process group → clean stop
        )
    except Exception as e:
        return f"Error starting process: {e}"

    pid = f"proc{next(_counter)}"
    with _lock:
        _PROCS[pid] = {"proc": proc, "output": deque(maxlen=_MAX_LINES),
                       "command": cmd, "started": time.time()}
    threading.Thread(target=_pump, args=(pid, proc.stdout), daemon=True).start()

    time.sleep(1.8)  # let it boot (or fail fast) so the first read is useful
    alive = proc.poll() is None
    tail = "\n".join(list(_PROCS[pid]["output"])[-25:])
    if alive:
        status = (f"running in the background as '{pid}'. Use read_process('{pid}') to see "
                  f"more logs and stop_process('{pid}') when done. If it serves HTTP, test "
                  f"it with http_request now.")
    else:
        status = f"exited immediately with code {proc.returncode} — check the output below."
    return f"$ {cmd}\n[{status}]\n--- output so far ---\n{tail or '[no output yet]'}"


def read_process(id: str, lines: int = 80) -> str:
    """Return the most recent output (and live status) of a background process."""
    info = _PROCS.get((id or "").strip())
    if not info:
        return f"Error: no process '{id}'. Active: {', '.join(_PROCS) or 'none'}."
    proc = info["proc"]
    alive = proc.poll() is None
    try:
        n = max(1, int(lines or 80))
    except (TypeError, ValueError):
        n = 80
    out = list(info["output"])[-n:]
    status = "running" if alive else f"exited (code {proc.returncode})"
    return f"[{id}] $ {info['command']} — {status}\n" + ("\n".join(out) or "[no output yet]")


def stop_process(id: str) -> str:
    """Terminate a background process (and its whole process group)."""
    info = _PROCS.get((id or "").strip())
    if not info:
        return f"Error: no process '{id}'. Active: {', '.join(_PROCS) or 'none'}."
    proc = info["proc"]
    if proc.poll() is None:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(os.getpgid(proc.pid), sig)
            except ProcessLookupError:
                break
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
                break
            try:
                proc.wait(timeout=4)
                break
            except subprocess.TimeoutExpired:
                continue
    return f"Stopped '{info['command']}' ({id})."


def list_processes() -> str:
    """List background processes started this session and whether they're alive."""
    if not _PROCS:
        return "No background processes."
    rows = []
    for pid, info in _PROCS.items():
        alive = info["proc"].poll() is None
        rows.append(f"- {pid}: $ {info['command']} — {'running' if alive else 'exited'}")
    return "\n".join(rows)
