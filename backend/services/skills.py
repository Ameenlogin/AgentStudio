"""Skills — reusable capability packs the agent can follow, à la Claude Code.

A skill is a folder under ``backend/skills/`` containing a ``SKILL.md`` (or
``README.md``) describing how to do something well. The agent is told which
skills exist and reads the full guide before a matching task. Users can install
new skills from any public GitHub repo (``install_from_github``); the repo's
SKILL.md/README becomes the skill.

This module ships a curated starter set focused on design & document quality.
"""
from __future__ import annotations

import os
import re
import subprocess

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")
_GUIDE_NAMES = ("SKILL.md", "skill.md", "README.md", "readme.md")


def _ensure_dir() -> None:
    os.makedirs(SKILLS_DIR, exist_ok=True)


def _guide_path(folder: str) -> str | None:
    for n in _GUIDE_NAMES:
        p = os.path.join(folder, n)
        if os.path.isfile(p):
            return p
    return None


def _read_head(path: str, lines: int = 6) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read(4000)
    except Exception:
        return ""
    # description = first non-heading, non-empty line(s)
    out = []
    for ln in text.splitlines():
        s = ln.strip().lstrip("#").strip()
        if s and not s.startswith("!["):
            out.append(s)
        if len(out) >= 2:
            break
    return " ".join(out)[:200]


def list_skills() -> list[dict]:
    _ensure_dir()
    skills = []
    for name in sorted(os.listdir(SKILLS_DIR)):
        folder = os.path.join(SKILLS_DIR, name)
        if not os.path.isdir(folder):
            continue
        guide = _guide_path(folder)
        if not guide:
            continue
        skills.append({
            "name": name,
            "description": _read_head(guide),
            "guide": os.path.relpath(guide, SKILLS_DIR),
        })
    return skills


def read_skill(name: str) -> str:
    _ensure_dir()
    safe = os.path.basename(name.strip().rstrip("/"))
    folder = os.path.join(SKILLS_DIR, safe)
    if not os.path.isdir(folder):
        return f"Error: skill '{safe}' not found. Installed: {', '.join(s['name'] for s in list_skills()) or 'none'}."
    guide = _guide_path(folder)
    if not guide:
        return f"Error: skill '{safe}' has no SKILL.md/README."
    try:
        with open(guide, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(20000)
    except Exception as e:
        return f"Error reading skill: {e}"


def _safe_name_from_url(url: str) -> str:
    name = url.rstrip("/").split("/")[-1]
    name = re.sub(r"\.git$", "", name)
    name = re.sub(r"[^A-Za-z0-9._-]", "-", name) or "skill"
    return name[:60]


def install_from_github(url: str) -> str:
    """Clone a public GitHub repo into the skills directory and register it."""
    _ensure_dir()
    url = (url or "").strip()
    if not re.match(r"^https?://(www\.)?(github|gitlab)\.com/[\w.-]+/[\w.-]+", url):
        return "Error: provide a public GitHub/GitLab repo URL (https://github.com/owner/repo)."
    if not url.endswith(".git") and "/tree/" not in url:
        clone_url = url + ".git"
    else:
        clone_url = url
    name = _safe_name_from_url(url)
    dest = os.path.join(SKILLS_DIR, name)
    if os.path.isdir(dest):
        return f"Skill '{name}' is already installed. Use read_skill('{name}') to view it."
    try:
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, dest],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            return f"Error cloning skill: {(proc.stderr or '').strip()[:600]}"
    except FileNotFoundError:
        return "Error: git is not installed."
    except subprocess.TimeoutExpired:
        return "Error: clone timed out."
    guide = _guide_path(dest)
    if not guide:
        return (f"Installed '{name}', but it has no SKILL.md/README. The agent can "
                f"still browse it with list_directory/read_file under skills/{name}.")
    return f"Installed skill '{name}'. Description: {_read_head(guide)}"


def skills_prompt() -> str:
    """A system-prompt section advertising installed skills."""
    skills = list_skills()
    if not skills:
        return ""
    lines = [
        "SKILLS — reusable expertise packs. Before a task that matches one, call "
        "read_skill('<name>') and follow its guidance. If the user pastes a GitHub "
        "repo URL, install it as a skill with install_skill('<url>') and follow it.",
        "Available skills:",
    ]
    for s in skills:
        desc = s["description"] or "(see guide)"
        lines.append(f"- {s['name']}: {desc}")
    return "\n".join(lines)
