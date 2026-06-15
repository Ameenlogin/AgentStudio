"""Real Chrome browser control for the agent (Playwright).

This is what lets the agent drive a *real* Chromium instance — navigate, click,
type, fill forms, scroll, read the DOM/accessibility tree, take screenshots for
visual grounding, do coordinate-based (vision) clicks, juggle tabs, upload files,
and persist a logged-in session across steps and tasks.

WHY A DEDICATED THREAD
----------------------
Playwright's *sync* API objects are thread-affine: a browser created on one
thread cannot be touched from another. But the agent loop runs each tool call in
its own ``asyncio.to_thread`` worker, so successive ``browser_*`` calls land on
*different* threads. To keep one persistent browser/page alive across calls we
run a single long-lived worker thread that owns the Playwright instance and
processes a command queue — every browser operation is marshalled onto that one
thread. This mirrors how ``process_tools`` keeps per-session background processes
alive, but adapted to Playwright's threading rules.

Playwright itself is imported lazily *inside the worker thread* so the rest of
the app boots fine even when Playwright (or its Chromium download) isn't yet
installed; the tools then return a clear, actionable install hint instead of
crashing the import graph.
"""
from __future__ import annotations

import os
import time
import queue
import threading
import concurrent.futures
from tools.sandbox import get_workspace, resolve, rel

# ── Tunables ──────────────────────────────────────────────────────────────────
_DEFAULT_TIMEOUT_MS = 30_000          # per-action Playwright timeout
_NAV_TIMEOUT_MS = 45_000              # navigation can be slower
_SHOT_DIR = "browser_screenshots"      # inside the workspace (visible/downloadable)
_PROFILE_DIR = ".agent_browser/profile"   # persistent Chrome profile (cookies survive)
_SESSION_DIR = ".agent_browser/sessions"  # named cookie/storage snapshots

_INSTALL_HINT = (
    "The Playwright browser isn't ready yet. Install it once with:\n"
    "  install_package('playwright')  then  run_command('playwright install chromium')\n"
    "After that, browser tools will launch a real Chrome automatically."
)


# ── Single-thread Playwright manager ───────────────────────────────────────────
class _Browser:
    """Owns one persistent Chromium context on a dedicated worker thread."""

    def __init__(self) -> None:
        self._q: "queue.Queue" = queue.Queue()
        self._thread: threading.Thread | None = None
        self._start_lock = threading.Lock()
        # Playwright handles (only ever touched on the worker thread)
        self._pw = None
        self._context = None
        self._page = None          # the active page
        self._headless = True
        self._shot_seq = 0
        self._workspace = None

    # -- worker thread plumbing -------------------------------------------------
    def _ensure_thread(self) -> None:
        with self._start_lock:
            if self._thread and self._thread.is_alive():
                return
            t = threading.Thread(target=self._loop, name="browser-worker", daemon=True)
            t.start()
            self._thread = t

    def _loop(self) -> None:
        while True:
            job = self._q.get()
            if job is None:
                break
            fn, fut = job
            try:
                fut.set_result(fn())
            except Exception as e:  # noqa: BLE001 — surfaced to the caller's Future
                fut.set_exception(e)

    def run(self, fn, timeout: float = 75.0):
        """Marshal ``fn`` onto the browser thread and wait for its result."""
        self._ensure_thread()
        fut: concurrent.futures.Future = concurrent.futures.Future()
        self._q.put((fn, fut))
        try:
            return fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return "Error: browser operation timed out."

    # -- lifecycle (always called on the worker thread) ------------------------
    def _launch(self, headless: bool):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            raise RuntimeError(_INSTALL_HINT)
        self._workspace = get_workspace()
        profile = os.path.join(self._workspace, _PROFILE_DIR)
        os.makedirs(profile, exist_ok=True)
        self._pw = sync_playwright().start()
        # Persistent context → cookies/localStorage survive across tasks (stay logged in).
        self._context = self._pw.chromium.launch_persistent_context(
            profile,
            headless=headless,
            viewport={"width": 1280, "height": 800},
            args=["--no-first-run", "--no-default-browser-check", "--start-maximized"],
            ignore_https_errors=True,
        )
        self._context.set_default_timeout(_DEFAULT_TIMEOUT_MS)
        self._context.set_default_navigation_timeout(_NAV_TIMEOUT_MS)
        self._headless = headless
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        return self._page

    def _ensure_page(self):
        """Lazily launch (headless) so callers can `browser_goto` without a launch."""
        if self._context is None or self._page is None:
            self._launch(self._headless)
        # Drop pages that were closed by the site (window.close / target gone).
        if self._page and self._page.is_closed():
            live = [p for p in self._context.pages if not p.is_closed()]
            self._page = live[-1] if live else self._context.new_page()
        return self._page

    def _new_shot_path(self) -> tuple[str, str]:
        self._shot_seq += 1
        ws = self._workspace or get_workspace()
        out_dir = os.path.join(ws, _SHOT_DIR)
        os.makedirs(out_dir, exist_ok=True)
        abs_path = os.path.join(out_dir, f"shot_{self._shot_seq:03d}.png")
        return abs_path, rel(abs_path)

    def _state(self, note: str = "") -> str:
        """A compact, model-friendly status line for the current page."""
        p = self._page
        try:
            title = p.title()
        except Exception:
            title = ""
        url = ""
        try:
            url = p.url
        except Exception:
            pass
        ntabs = len([t for t in (self._context.pages if self._context else []) if not t.is_closed()])
        head = f"{note}\n" if note else ""
        return f"{head}● {title or '(untitled)'} — {url}\n[{ntabs} tab(s) open]"


_B = _Browser()


# ── Helpers shared by the tool functions ───────────────────────────────────────
def _truncate(text: str, limit: int = 9000) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "\n…[truncated]"


# Fallback role/label outline, derived straight from the DOM. Used when the
# Playwright ARIA snapshot API isn't available on the installed version.
_AXTREE_JS = r"""
() => {
  const out = [];
  const sel = 'h1,h2,h3,h4,a,button,input,textarea,select,[role=button],[role=link],[role=heading],nav,main,form,label';
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect();
    if (r.width < 1 && r.height < 1) continue;
    const tag = el.tagName.toLowerCase();
    let role = el.getAttribute('role') || ({h1:'heading',h2:'heading',h3:'heading',h4:'heading',
      a:'link',button:'button',input:'textbox',textarea:'textbox',select:'combobox',
      nav:'navigation',main:'main',form:'form',label:'label'}[tag] || tag);
    let name = (el.getAttribute('aria-label') || el.value || el.placeholder ||
                el.innerText || el.alt || el.title || '').trim().replace(/\s+/g,' ');
    if (name.length > 80) name = name.slice(0,80) + '…';
    out.push(name ? `${role} "${name}"` : role);
    if (out.length >= 160) break;
  }
  return out.join('\n');
}
"""


# JS that lists the visible, interactive elements with their on-screen centre —
# the coordinates the model can feed to browser_click_at / browser_type_at.
_INTERACTIVE_JS = r"""
() => {
  const sel = 'a,button,input,textarea,select,[role=button],[role=link],[role=tab],[role=menuitem],[onclick],[contenteditable=true]';
  const out = [];
  const seen = new Set();
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) continue;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none' || +st.opacity === 0) continue;
    let label = (el.getAttribute('aria-label') || el.value || el.placeholder ||
                 el.innerText || el.alt || el.title || '').trim().replace(/\s+/g, ' ');
    if (label.length > 70) label = label.slice(0, 70) + '…';
    const key = el.tagName + '|' + label + '|' + Math.round(r.x) + ',' + Math.round(r.y);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      tag: el.tagName.toLowerCase(),
      type: el.getAttribute('type') || el.getAttribute('role') || '',
      label,
      x: Math.round(r.x + r.width / 2),
      y: Math.round(r.y + r.height / 2),
    });
    if (out.length >= 60) break;
  }
  return out;
}
"""


def _interactive_list() -> str:
    try:
        items = _B._page.evaluate(_INTERACTIVE_JS)
    except Exception:
        return ""
    if not items:
        return ""
    lines = [
        f"  [{i}] {it['tag']}{('/' + it['type']) if it['type'] else ''} "
        f'"{it["label"]}" @ ({it["x"]},{it["y"]})'
        for i, it in enumerate(items)
    ]
    return "INTERACTIVE ELEMENTS (use browser_click_at(x,y) to act on coordinates):\n" + "\n".join(lines)


# ── Public tool functions (each marshalled onto the browser thread) ─────────────
def browser_launch(url: str = "", headless: bool = True) -> str:
    """Launch (or relaunch) a real Chromium and optionally open a URL."""
    def _do():
        # Relaunch only if the headless mode changed; otherwise reuse the session.
        if _B._context is not None and bool(headless) != _B._headless:
            try:
                _B._context.close()
                _B._pw.stop()
            except Exception:
                pass
            _B._context = _B._page = _B._pw = None
        _B._headless = bool(headless)
        _B._ensure_page()
        if url:
            _B._page.goto(url, wait_until="domcontentloaded")
        mode = "headless" if headless else "headful (visible) — complete any login/2FA here"
        return _B._state(f"Chrome launched ({mode}).")
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error launching browser: {e}"


def browser_goto(url: str, wait_until: str = "load") -> str:
    if not url:
        return "Error: provide a URL."
    if not url.startswith(("http://", "https://", "file://", "about:")):
        url = "https://" + url

    def _do():
        p = _B._ensure_page()
        wu = wait_until if wait_until in ("load", "domcontentloaded", "commit", "networkidle") else "load"
        p.goto(url, wait_until=wu)
        return _B._state(f"Navigated to {url}.")
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error navigating to {url}: {e}"


def browser_back() -> str:
    try:
        return _B.run(lambda: (_B._ensure_page().go_back(), _B._state("Went back."))[1])
    except Exception as e:
        return f"Error going back: {e}"


def browser_forward() -> str:
    try:
        return _B.run(lambda: (_B._ensure_page().go_forward(), _B._state("Went forward."))[1])
    except Exception as e:
        return f"Error going forward: {e}"


def browser_reload() -> str:
    try:
        return _B.run(lambda: (_B._ensure_page().reload(), _B._state("Reloaded."))[1])
    except Exception as e:
        return f"Error reloading: {e}"


def browser_click(selector: str) -> str:
    if not selector:
        return "Error: provide a CSS/text selector."

    def _do():
        p = _B._ensure_page()
        p.click(selector)
        p.wait_for_load_state("domcontentloaded")
        return _B._state(f"Clicked {selector}.")
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error clicking '{selector}': {e}"


def browser_click_at(x: int, y: int) -> str:
    """Vision-grounded click at viewport coordinates (from the interactive list)."""
    def _do():
        p = _B._ensure_page()
        p.mouse.click(float(x), float(y))
        p.wait_for_load_state("domcontentloaded")
        return _B._state(f"Clicked at ({x}, {y}).")
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error clicking at ({x}, {y}): {e}"


def browser_type(selector: str, text: str, submit: bool = False) -> str:
    """Focus an element, type text, optionally press Enter to submit."""
    if not selector:
        return "Error: provide a selector."

    def _do():
        p = _B._ensure_page()
        p.fill(selector, text)
        if submit:
            p.press(selector, "Enter")
            p.wait_for_load_state("domcontentloaded")
        return _B._state(f"Typed into {selector}{' and submitted' if submit else ''}.")
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error typing into '{selector}': {e}"


def browser_type_at(x: int, y: int, text: str, submit: bool = False) -> str:
    """Vision-grounded typing: click coordinates, then type (optionally submit)."""
    def _do():
        p = _B._ensure_page()
        p.mouse.click(float(x), float(y))
        p.keyboard.type(text)
        if submit:
            p.keyboard.press("Enter")
            p.wait_for_load_state("domcontentloaded")
        return _B._state(f"Typed at ({x}, {y}){' and submitted' if submit else ''}.")
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error typing at ({x}, {y}): {e}"


def browser_fill(selector: str, text: str) -> str:
    """Set a form field's value without submitting."""
    return browser_type(selector, text, submit=False)


def browser_select_option(selector: str, value: str) -> str:
    def _do():
        p = _B._ensure_page()
        p.select_option(selector, value)
        return _B._state(f"Selected '{value}' in {selector}.")
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error selecting option in '{selector}': {e}"


def browser_hover(selector: str) -> str:
    def _do():
        p = _B._ensure_page()
        p.hover(selector)
        return _B._state(f"Hovered {selector}.")
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error hovering '{selector}': {e}"


def browser_drag(source: str, target: str) -> str:
    def _do():
        p = _B._ensure_page()
        p.drag_and_drop(source, target)
        return _B._state(f"Dragged {source} → {target}.")
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error dragging '{source}' → '{target}': {e}"


def browser_scroll(direction: str = "down", amount: int = 600) -> str:
    def _do():
        p = _B._ensure_page()
        dy = {"down": amount, "up": -amount}.get(direction, amount)
        dx = {"right": amount, "left": -amount}.get(direction, 0)
        if direction in ("up", "down"):
            dx = 0
        elif direction in ("left", "right"):
            dy = 0
        p.mouse.wheel(dx, dy)
        p.wait_for_timeout(250)
        return _B._state(f"Scrolled {direction} {amount}px.")
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error scrolling: {e}"


def browser_key_press(key: str) -> str:
    """Press a key or chord, e.g. 'Enter', 'Escape', 'Tab', 'Control+A'."""
    if not key:
        return "Error: provide a key."

    def _do():
        p = _B._ensure_page()
        p.keyboard.press(key)
        p.wait_for_load_state("domcontentloaded")
        return _B._state(f"Pressed {key}.")
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error pressing '{key}': {e}"


def browser_get_content(selector: str = "", max_chars: int = 9000) -> str:
    """Readable text of the page (or a region). The model's primary 'eyes'."""
    def _do():
        p = _B._ensure_page()
        if selector:
            try:
                txt = "\n".join(t for t in p.locator(selector).all_inner_texts())
            except Exception:
                txt = p.inner_text(selector)
        else:
            txt = p.evaluate("() => document.body ? document.body.innerText : ''")
        return f"{_B._state()}\n\n--- PAGE TEXT ---\n{_truncate(txt, max_chars)}"
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error reading page: {e}"


def browser_get_accessibility_tree() -> str:
    """A lightweight, text-only view of the page: accessibility roles/labels plus
    the on-screen coordinates of interactive elements (for vision-grounded clicks)."""
    def _do():
        p = _B._ensure_page()
        tree = ""
        try:
            # Modern Playwright: a compact YAML-ish ARIA snapshot of the page.
            tree = p.locator("body").aria_snapshot()
        except Exception:
            try:
                tree = p.evaluate(_AXTREE_JS)
            except Exception:
                tree = ""
        tree = tree or "(no accessibility nodes)"
        inter = _interactive_list()
        body = f"{_B._state()}\n\n--- ACCESSIBILITY TREE ---\n{_truncate(tree, 6000)}"
        if inter:
            body += "\n\n" + _truncate(inter, 4000)
        return body
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error reading accessibility tree: {e}"


def browser_screenshot(selector: str = "", full_page: bool = False, highlight: str = "") -> str:
    """Capture the page (or one element) to a PNG in the workspace and reference it
    so the timeline renders it inline. Optional `highlight` outlines a selector."""
    def _do():
        p = _B._ensure_page()
        abs_path, rel_path = _B._new_shot_path()
        added_highlight = False
        if highlight:
            try:
                p.eval_on_selector(
                    highlight,
                    "el => { el.setAttribute('data-ac-hl', el.style.outline || 'none');"
                    " el.style.outline = '3px solid #ff5d3b'; el.style.outlineOffset = '2px'; }",
                )
                added_highlight = True
            except Exception:
                pass
        try:
            if selector:
                p.locator(selector).first.screenshot(path=abs_path)
            else:
                p.screenshot(path=abs_path, full_page=bool(full_page))
        finally:
            if added_highlight:
                try:
                    p.eval_on_selector(highlight, "el => { el.style.outline = ''; }")
                except Exception:
                    pass
        try:
            w, h = p.viewport_size["width"], p.viewport_size["height"]
            dims = f" ({w}×{h})"
        except Exception:
            dims = ""
        # The trailing IMAGE: line is parsed by the frontend Browser app and
        # rendered as the live page view inside the Agent Computer.
        return f"{_B._state(f'Screenshot saved{dims}.')}\nIMAGE: {rel_path}"
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error taking screenshot: {e}"


def browser_find_element(text: str) -> str:
    """Locate an element by visible text or selector; report whether it exists
    and where it is on screen (centre coordinates)."""
    if not text:
        return "Error: provide text or a selector to find."

    def _do():
        p = _B._ensure_page()
        loc = None
        for attempt in (
            lambda: p.get_by_text(text, exact=False).first,
            lambda: p.get_by_role("button", name=text).first,
            lambda: p.locator(text).first,
        ):
            try:
                cand = attempt()
                if cand.count() > 0:
                    loc = cand
                    break
            except Exception:
                continue
        if not loc:
            return f"Not found: '{text}'."
        try:
            box = loc.bounding_box()
            inner = (loc.inner_text() or "").strip().replace("\n", " ")[:80]
            if box:
                cx = int(box["x"] + box["width"] / 2)
                cy = int(box["y"] + box["height"] / 2)
                return f"Found '{text}': \"{inner}\" @ ({cx},{cy}). Use browser_click_at({cx},{cy})."
            return f"Found '{text}' (off-screen): \"{inner}\"."
        except Exception:
            return f"Found '{text}'."
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error finding '{text}': {e}"


def browser_wait_for_selector(selector: str, timeout: int = 15, state: str = "visible") -> str:
    if not selector:
        return "Error: provide a selector."

    def _do():
        p = _B._ensure_page()
        st = state if state in ("attached", "detached", "visible", "hidden") else "visible"
        p.wait_for_selector(selector, timeout=int(timeout) * 1000, state=st)
        return _B._state(f"'{selector}' is {st}.")
    try:
        return _B.run(_do, timeout=float(timeout) + 20)
    except Exception as e:
        return f"Error waiting for '{selector}': {e}"


def browser_wait_for_text(text: str, timeout: int = 15) -> str:
    if not text:
        return "Error: provide text to wait for."

    def _do():
        p = _B._ensure_page()
        p.get_by_text(text, exact=False).first.wait_for(
            timeout=int(timeout) * 1000, state="visible")
        return _B._state(f"Text '{text}' appeared.")
    try:
        return _B.run(_do, timeout=float(timeout) + 20)
    except Exception as e:
        return f"Error waiting for text '{text}': {e}"


def browser_wait_for_navigation(timeout: int = 15) -> str:
    def _do():
        p = _B._ensure_page()
        p.wait_for_load_state("networkidle", timeout=int(timeout) * 1000)
        return _B._state("Page settled (network idle).")
    try:
        return _B.run(_do, timeout=float(timeout) + 20)
    except Exception as e:
        return f"Error waiting for navigation: {e}"


# ── Tabs ────────────────────────────────────────────────────────────────────
def browser_new_tab(url: str = "") -> str:
    def _do():
        _B._ensure_page()
        page = _B._context.new_page()
        _B._page = page
        if url:
            if not url.startswith(("http://", "https://", "about:", "file://")):
                url = "https://" + url
            page.goto(url, wait_until="domcontentloaded")
        return _B._state("Opened a new tab.")
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error opening new tab: {e}"


def browser_switch_tab(index: int) -> str:
    def _do():
        _B._ensure_page()
        pages = [t for t in _B._context.pages if not t.is_closed()]
        i = int(index)
        if i < 0 or i >= len(pages):
            return f"Error: tab {i} doesn't exist (have {len(pages)})."
        _B._page = pages[i]
        _B._page.bring_to_front()
        return _B._state(f"Switched to tab {i}.")
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error switching tab: {e}"


def browser_close_tab(index: int = -1) -> str:
    def _do():
        _B._ensure_page()
        pages = [t for t in _B._context.pages if not t.is_closed()]
        i = int(index)
        target = _B._page if i < 0 else (pages[i] if 0 <= i < len(pages) else None)
        if target is None:
            return f"Error: tab {i} doesn't exist."
        target.close()
        live = [t for t in _B._context.pages if not t.is_closed()]
        _B._page = live[-1] if live else _B._context.new_page()
        return _B._state("Closed tab.")
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error closing tab: {e}"


def browser_list_tabs() -> str:
    def _do():
        _B._ensure_page()
        pages = [t for t in _B._context.pages if not t.is_closed()]
        rows = []
        for i, t in enumerate(pages):
            mark = "→" if t is _B._page else " "
            try:
                rows.append(f"{mark} [{i}] {t.title()[:50]} — {t.url}")
            except Exception:
                rows.append(f"{mark} [{i}] {t.url}")
        return "Open tabs:\n" + "\n".join(rows)
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error listing tabs: {e}"


def browser_upload_file(selector: str, path: str) -> str:
    """Set a file <input> to a workspace file (for upload forms)."""
    if not selector or not path:
        return "Error: provide a selector and a workspace file path."

    def _do():
        p = _B._ensure_page()
        abs_path = resolve(path)
        if not os.path.isfile(abs_path):
            return f"Error: file not found: {path}"
        p.set_input_files(selector, abs_path)
        return _B._state(f"Attached {rel(abs_path)} to {selector}.")
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error uploading file: {e}"


# ── Session / auth persistence ─────────────────────────────────────────────────
def browser_save_session(name: str = "default") -> str:
    """Snapshot cookies + storage so an authenticated session can be restored."""
    def _do():
        _B._ensure_page()
        ws = _B._workspace or get_workspace()
        out_dir = os.path.join(ws, _SESSION_DIR)
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{name or 'default'}.json")
        _B._context.storage_state(path=path)
        return f"Saved browser session '{name}' to {rel(path)} (cookies + storage)."
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error saving session: {e}"


def browser_load_session(name: str = "default") -> str:
    """Restore cookies from a saved session so logins survive across tasks."""
    def _do():
        _B._ensure_page()
        ws = _B._workspace or get_workspace()
        path = os.path.join(ws, _SESSION_DIR, f"{name or 'default'}.json")
        if not os.path.isfile(path):
            return f"Error: no saved session '{name}'. Save one first with browser_save_session."
        import json as _json
        with open(path, "r", encoding="utf-8") as f:
            state = _json.load(f)
        cookies = state.get("cookies", [])
        if cookies:
            _B._context.add_cookies(cookies)
        return f"Loaded session '{name}' ({len(cookies)} cookie(s)). Reload the page to apply."
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error loading session: {e}"


def browser_close() -> str:
    """Close the browser and free its resources."""
    def _do():
        try:
            if _B._context is not None:
                _B._context.close()
            if _B._pw is not None:
                _B._pw.stop()
        finally:
            _B._context = _B._page = _B._pw = None
        return "Browser closed."
    try:
        return _B.run(_do)
    except Exception as e:
        return f"Error closing browser: {e}"
