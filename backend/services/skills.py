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


def _parse_frontmatter(text: str) -> dict:
    """Parse a leading YAML '--- name: … description: … ---' block, as used by
    Claude-style skills, so installed skills show their proper name/description."""
    meta: dict = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            for ln in text[3:end].splitlines():
                if ":" in ln:
                    k, _, v = ln.partition(":")
                    meta[k.strip().lower()] = v.strip().strip('"\'')
    return meta


def _meta(path: str) -> dict:
    """Return {'display', 'description'} for a skill guide.

    Honors a Claude-style YAML frontmatter block (``name`` / ``description``) and,
    when it is absent, falls back to the first ``# Heading`` for the display name
    and the next prose line(s) for the description."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read(8000)
    except Exception:
        return {"display": "", "description": ""}
    fm = _parse_frontmatter(text)
    display = fm.get("name", "")
    desc = fm.get("description", "")
    if not display or not desc:
        body = text
        if text.startswith("---"):
            e = text.find("\n---", 3)
            if e != -1:
                body = text[e + 4:]
        out = []
        for ln in body.splitlines():
            s = ln.strip()
            if not display and s.startswith("# "):
                display = s[2:].strip()
                continue
            t = s.lstrip("#").strip()
            if t and not t.startswith("!["):
                out.append(t)
            if len(out) >= 2:
                break
        if not desc:
            desc = " ".join(out)
    return {"display": display, "description": desc[:200]}


def list_skills() -> list[dict]:
    _ensure_dir()
    skills = []
    for name in sorted(os.listdir(SKILLS_DIR)):
        folder = os.path.join(SKILLS_DIR, name)
        if not os.path.isdir(folder):
            continue
        # A real skill must declare itself with a SKILL.md manifest. This is what
        # stops an ordinary cloned repo (which only has a README) from being
        # mistaken for an installed skill and cluttering the Skills list.
        guide = None
        for n in ("SKILL.md", "skill.md"):
            p = os.path.join(folder, n)
            if os.path.isfile(p):
                guide = p
                break
        if not guide:
            continue
        m = _meta(guide)
        skills.append({
            "name": name,
            "display": m["display"] or name,
            "description": m["description"],
            "guide": os.path.relpath(guide, SKILLS_DIR),
        })
    return skills


def resolve_skill(query: str) -> str | None:
    """Map a user-typed token (e.g. '/design') to an installed skill folder.
    Tolerant: exact, then prefix, then substring — on folder OR display name."""
    q = (query or "").strip().lstrip("/").lower()
    if not q:
        return None
    skills = list_skills()
    for s in skills:
        if s["name"].lower() == q or (s["display"] or "").lower() == q:
            return s["name"]
    for s in skills:
        if s["name"].lower().startswith(q) or (s["display"] or "").lower().startswith(q):
            return s["name"]
    for s in skills:
        if q in s["name"].lower() or q in (s["display"] or "").lower():
            return s["name"]
    return None


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
    return f"Installed skill '{name}'. Description: {_meta(guide)['description']}"


def skills_prompt() -> str:
    """A system-prompt section advertising installed skills."""
    skills = list_skills()
    if not skills:
        return ""
    lines = [
        "SKILLS — reusable expertise packs the user has installed. Before a task that "
        "clearly matches one, call read_skill('<name>') and follow its guidance. "
        "IMPORTANT: do NOT install skills on your own. Only call install_skill when the "
        "user EXPLICITLY asks to add or install a skill. A GitHub URL the user wants you "
        "to work on (clone, fix, build, review, run) is an ordinary coding task — clone "
        "it with `git clone` via run_command and work in the clone; never treat it as a "
        "skill to install.",
        "Available skills:",
    ]
    for s in skills:
        desc = s["description"] or "(see guide)"
        lines.append(f"- {s['name']}: {desc}")
    return "\n".join(lines)
