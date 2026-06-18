"""VerificationEngine — run real checks and report structured pass/fail so the
agent can PROVE its work runs before claiming a task is done.

Verification is non-negotiable in the Grok-power model: after building, the agent
calls ``verify_work`` which runs tests / a build / a compile in the workspace and
returns a clean PASSED / FAILED verdict plus the relevant output tail. It reuses
the sandboxed shell runner so everything stays inside the workspace root.
"""
import os
from tools.sandbox import get_workspace
from tools.shell_tools import run_command


# Auto-detection order: the first command whose tooling is present in the
# workspace is used when the caller doesn't name a framework explicitly.
def _detect_command() -> tuple[str, str] | None:
    ws = get_workspace()

    def has(*names) -> bool:
        return any(os.path.exists(os.path.join(ws, n)) for n in names)

    # Node / JS / TS project with a test script.
    if has("package.json"):
        try:
            import json
            with open(os.path.join(ws, "package.json"), "r", encoding="utf-8") as f:
                pkg = json.load(f)
            scripts = pkg.get("scripts", {}) or {}
            if "test" in scripts:
                return "npm test", "npm"
            if "build" in scripts:
                return "npm run build", "npm"
        except Exception:
            pass
        return "npm test", "npm"
    # Python project / test suite.
    if has("pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg", "tests", "test"):
        return "python -m pytest -q", "pytest"
    # Go.
    if has("go.mod"):
        return "go test ./...", "go"
    # Rust.
    if has("Cargo.toml"):
        return "cargo test", "cargo"
    # Makefile with a test target.
    if has("Makefile", "makefile"):
        return "make test", "make"
    return None


_FRAMEWORK_CMD = {
    "pytest": "python -m pytest -q",
    "python": "python -m pytest -q",
    "npm": "npm test",
    "node": "npm test",
    "jest": "npx jest",
    "vitest": "npx vitest run",
    "build": "npm run build",
    "go": "go test ./...",
    "cargo": "cargo test",
    "make": "make test",
}


def _verdict(output: str) -> bool:
    """Decide pass/fail from the sandbox runner's '(exit code N)' line plus a few
    well-known failure markers, so a zero-exit-but-failing run is still caught."""
    text = output or ""
    passed = "(exit code 0)" in text
    low = text.lower()
    bad_markers = (
        "failed", "error:", "assertionerror", "traceback (most recent call last)",
        "test failed", "build failed", "✗", "fail ", " failures",
    )
    if passed and any(m in low for m in bad_markers):
        # Heuristic: explicit "0 failed" / "0 errors" is still a pass.
        if not any(g in low for g in ("0 failed", "0 errors", "0 failures", "passed")):
            passed = False
    return passed


def verify_work(command: str = "", framework: str = "") -> str:
    """Run a verification command (or auto-detect one) and return a structured
    report: a one-line verdict, the command, and the output tail."""
    cmd = (command or "").strip()
    fw = (framework or "").strip().lower()
    if not cmd and fw:
        cmd = _FRAMEWORK_CMD.get(fw, "")
    detected = ""
    if not cmd:
        found = _detect_command()
        if found:
            cmd, detected = found[0], found[1]
    if not cmd:
        return (
            "VERIFICATION: no command. I couldn't auto-detect a test/build setup in "
            "the workspace. Pass an explicit `command` (e.g. \"python -m pytest -q\", "
            "\"npm test\", \"python app.py\") or a `framework` (pytest | npm | build | "
            "go | cargo | make)."
        )

    output = run_command(cmd)
    passed = _verdict(output)
    verdict = "✅ PASSED" if passed else "❌ FAILED"
    head = f"VERIFICATION {verdict} — `{cmd}`"
    if detected:
        head += f" (auto-detected: {detected})"
    if not passed:
        head += "\nThe check did not pass. Read the output below, fix the cause, then verify again."
    return head + "\n\n" + (output or "[no output]")
