"""Run shell commands inside the workspace with a timeout. Supports both a
blocking call and a line-streaming variant for real-time stdout/stderr."""
import subprocess
import threading
from tools.sandbox import get_workspace

# Generous enough for real builds/installs (npm install, pip, compiles) that the
# old 60s cap killed mid-run. Output streams live and the user can always Stop.
TIMEOUT = 180


def run_command(command: str) -> str:
    if not command or not command.strip():
        return "Error: empty command."
    try:
        proc = subprocess.run(
            command, shell=True, cwd=get_workspace(),
            capture_output=True, text=True, timeout=TIMEOUT,
        )
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        parts = [f"$ {command}", f"(exit code {proc.returncode})"]
        if out:
            parts.append("--- stdout ---\n" + out[:8000])
        if err:
            parts.append("--- stderr ---\n" + err[:4000])
        if not out and not err:
            parts.append("[no output]")
        return "\n".join(parts)
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {TIMEOUT}s: {command}"
    except Exception as e:
        return f"Error running command: {e}"


def run_command_stream(command: str, on_line) -> str:
    """Run a command, invoking on_line(text) for each line of output as it
    arrives, and returning the full captured result string at the end."""
    if not command or not command.strip():
        return "Error: empty command."
    on_line(f"$ {command}\n")
    return _stream_process(["/bin/bash", "-lc", command], on_line, header=f"$ {command}")


def _stream_process(argv, on_line, header="") -> str:
    collected: list[str] = []

    def _pump(pipe, prefix):
        try:
            for line in iter(pipe.readline, ""):
                if not line:
                    break
                collected.append(line)
                on_line(line if not prefix else prefix + line)
        except Exception:
            pass
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    try:
        proc = subprocess.Popen(
            argv, cwd=get_workspace(), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
    except Exception as e:
        return f"Error running command: {e}"

    t = threading.Thread(target=_pump, args=(proc.stdout, ""), daemon=True)
    t.start()
    try:
        code = proc.wait(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        t.join(timeout=2)
        on_line(f"\n[timed out after {TIMEOUT}s]\n")
        return f"Error: command timed out after {TIMEOUT}s"
    t.join(timeout=2)
    body = "".join(collected).strip()
    tail = f"\n(exit code {code})"
    on_line(tail + "\n")
    out = (header + "\n" if header else "") + (body or "[no output]") + tail
    return out[:12000]
