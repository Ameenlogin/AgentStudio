"""Code execution tools — run Python snippets inside the workspace sandbox,
with a blocking call and a line-streaming variant for live output."""
import subprocess
import sys
import tempfile
import os
import re
from tools.sandbox import get_workspace
from tools.shell_tools import _stream_process

TIMEOUT = 90


def install_package(package: str) -> str:
    """pip-install one or more Python packages into the app's environment so the
    agent can self-equip for a task (e.g. lxml, pandas, pillow, playwright)."""
    pkg = (package or "").strip()
    if not pkg or not re.match(r"^[A-Za-z0-9_.\-\[\]<>=!,\s]+$", pkg):
        return "Error: invalid package specifier."
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", *pkg.split()],
            capture_output=True, text=True, timeout=240,
        )
        if proc.returncode == 0:
            tail = (proc.stdout or "").strip().splitlines()[-3:]
            return f"Installed: {pkg}\n" + "\n".join(tail)
        return f"pip install failed (exit {proc.returncode}):\n{(proc.stderr or proc.stdout)[-1500:]}"
    except subprocess.TimeoutExpired:
        return f"Error: installing {pkg} timed out."
    except Exception as e:
        return f"Error installing {pkg}: {e}"


def python_exec(code: str) -> str:
    """Execute a Python snippet in the workspace and return stdout/stderr."""
    if not code or not code.strip():
        return "Error: empty code."
    ws = get_workspace()
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", dir=ws, delete=False, encoding="utf-8") as tf:
            tf.write(code)
            tmp = tf.name
        try:
            proc = subprocess.run(
                [sys.executable, tmp],
                cwd=ws, capture_output=True, text=True, timeout=TIMEOUT,
            )
            out = (proc.stdout or "").strip()
            err = (proc.stderr or "").strip()
            parts = [f"(exit code {proc.returncode})"]
            if out:
                parts.append("--- stdout ---\n" + out[:8000])
            if err:
                parts.append("--- stderr ---\n" + err[:4000])
            if not out and not err:
                parts.append("[no output]")
            return "\n".join(parts)
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
    except subprocess.TimeoutExpired:
        return f"Error: code timed out after {TIMEOUT}s."
    except Exception as e:
        return f"Error executing code: {e}"


def python_exec_stream(code: str, on_line) -> str:
    """Run a Python snippet, streaming stdout/stderr line by line via on_line."""
    if not code or not code.strip():
        return "Error: empty code."
    ws = get_workspace()
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", dir=ws, delete=False, encoding="utf-8") as tf:
            tf.write(code)
            tmp = tf.name
    except Exception as e:
        return f"Error preparing code: {e}"
    try:
        return _stream_process([sys.executable, "-u", tmp], on_line, header="python ▸")
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
