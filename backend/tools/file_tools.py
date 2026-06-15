"""File system tools, all sandboxed to the workspace."""
import os
from tools.sandbox import resolve, rel

MAX_READ = 200_000  # chars — cap for a whole-file read
PAGE_LINES = 2000   # default lines returned by a ranged (offset/limit) read
MAX_SCAN_BYTES = 5_000_000  # skip files bigger than this in bulk grep/search scans


def _is_text_file(path: str) -> bool:
    """Cheap binary/oversize filter for bulk scans (grep / search / replace).

    Reading huge binaries line-by-line is what makes a search across a real
    project slow; a NUL-byte sniff + size cap skips them so scans stay fast and
    never return junk matches (or corrupt a binary on replace)."""
    try:
        if os.path.getsize(path) > MAX_SCAN_BYTES:
            return False
        with open(path, "rb") as f:
            return b"\x00" not in f.read(4096)
    except Exception:
        return False


def read_file(path: str, offset: int = 0, limit: int = 0) -> str:
    """Read a text file in the workspace.

    Whole-file by default. For LARGE files, pass ``offset`` (1-based start line)
    and/or ``limit`` (number of lines) to page through any range — the returned
    text is verbatim (no line-number prefixes) so it can be fed straight back
    into edit_file / apply_patch.
    """
    p = resolve(path)
    if not os.path.isfile(p):
        return f"Error: file not found: {rel(p)}"
    try:
        offset = int(offset or 0)
        limit = int(limit or 0)

        # ── Ranged, line-based read (large-file paging) ──────────────────────
        if offset or limit:
            start = max(offset, 1)
            count = limit if limit > 0 else PAGE_LINES
            out, last = [], 0
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if i < start:
                        continue
                    if i >= start + count:
                        last = i
                        break
                    out.append(line.rstrip("\n"))
            if not out:
                return f"[no lines at offset {start} in {rel(p)} — file has fewer lines]"
            body = "\n".join(out)
            if last:
                body += (f"\n\n[...more lines below. Continue with "
                         f"read_file(path, offset={start + count}).]")
            return body

        # ── Whole-file read with a generous char cap ─────────────────────────
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            data = f.read(MAX_READ + 1)
        if len(data) > MAX_READ:
            shown = data[:MAX_READ]
            return (shown + f"\n\n[...truncated at {MAX_READ} chars. This file is large — "
                    f"call read_file with offset/limit (1-based line numbers) to page "
                    f"through the rest, or use grep to jump to what you need.]")
        return data or "[file is empty]"
    except Exception as e:
        return f"Error reading {rel(p)}: {e}"


def write_file(path: str, content: str) -> str:
    p = resolve(path)
    try:
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content if content is not None else "")
        lines = (content or "").count("\n") + 1
        return f"Wrote {len(content or '')} chars ({lines} lines) to {rel(p)}"
    except Exception as e:
        return f"Error writing {rel(p)}: {e}"


def edit_file(path: str, find: str, replace: str) -> str:
    p = resolve(path)
    if not os.path.isfile(p):
        return f"Error: file not found: {rel(p)}"
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
        count = data.count(find)
        if count == 0:
            return f"Error: 'find' text not found in {rel(p)}. Read the file first to copy exact text."
        new = data.replace(find, replace)
        with open(p, "w", encoding="utf-8") as f:
            f.write(new)
        return f"Replaced {count} occurrence(s) in {rel(p)}"
    except Exception as e:
        return f"Error editing {rel(p)}: {e}"


def list_directory(path: str = ".") -> str:
    p = resolve(path)
    if not os.path.isdir(p):
        return f"Error: not a directory: {rel(p)}"
    try:
        entries = sorted(os.listdir(p))
        if not entries:
            return f"{rel(p)}/ is empty"
        out = []
        for name in entries:
            full = os.path.join(p, name)
            if os.path.isdir(full):
                out.append(f"[dir]  {name}/")
            else:
                size = os.path.getsize(full)
                out.append(f"[file] {name}  ({size} bytes)")
        return f"{rel(p)}/\n" + "\n".join(out)
    except Exception as e:
        return f"Error listing {rel(p)}: {e}"


def create_directory(path: str) -> str:
    p = resolve(path)
    try:
        os.makedirs(p, exist_ok=True)
        return f"Created directory {rel(p)}/"
    except Exception as e:
        return f"Error creating directory {rel(p)}: {e}"


def search_files(query: str, path: str = ".") -> str:
    root = resolve(path)
    hits = []
    skip = {".git", "node_modules", "__pycache__", "venv", "dist", ".venv"}
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                if not _is_text_file(fp):
                    continue
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if query in line:
                                hits.append(f"{rel(fp)}:{i}: {line.strip()[:200]}")
                                if len(hits) >= 100:
                                    raise StopIteration
                except StopIteration:
                    raise
                except Exception:
                    continue
    except StopIteration:
        pass
    if not hits:
        return f"No matches for '{query}' under {rel(root)}/"
    return "\n".join(hits[:100]) + ("" if len(hits) < 100 else "\n[...more matches truncated]")


# ── Extra file operations ─────────────────────────────────────────────────────
import shutil as _shutil


def append_file(path: str, content: str) -> str:
    p = resolve(path)
    try:
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(content or "")
        return f"Appended {len(content or '')} chars to {rel(p)}"
    except Exception as e:
        return f"Error appending to {rel(p)}: {e}"


def delete_path(path: str) -> str:
    p = resolve(path)
    try:
        if os.path.isdir(p):
            _shutil.rmtree(p)
            return f"Deleted directory {rel(p)}/"
        if os.path.isfile(p):
            os.remove(p)
            return f"Deleted file {rel(p)}"
        return f"Error: path not found: {rel(p)}"
    except Exception as e:
        return f"Error deleting {rel(p)}: {e}"


def move_path(src: str, dest: str) -> str:
    s = resolve(src)
    d = resolve(dest)
    try:
        os.makedirs(os.path.dirname(d) or ".", exist_ok=True)
        _shutil.move(s, d)
        return f"Moved {rel(s)} -> {rel(d)}"
    except Exception as e:
        return f"Error moving: {e}"


def copy_path(src: str, dest: str) -> str:
    s = resolve(src)
    d = resolve(dest)
    try:
        os.makedirs(os.path.dirname(d) or ".", exist_ok=True)
        if os.path.isdir(s):
            _shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            _shutil.copy2(s, d)
        return f"Copied {rel(s)} -> {rel(d)}"
    except Exception as e:
        return f"Error copying: {e}"


def file_info(path: str) -> str:
    p = resolve(path)
    if not os.path.exists(p):
        return f"Error: path not found: {rel(p)}"
    try:
        st = os.stat(p)
        kind = "directory" if os.path.isdir(p) else "file"
        import datetime as _dt
        mtime = _dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
        return f"{rel(p)} — {kind}, {st.st_size} bytes, modified {mtime}"
    except Exception as e:
        return f"Error stat {rel(p)}: {e}"


def replace_in_files(find: str, replace: str, path: str = ".", glob: str = "") -> str:
    """Find-and-replace across many files under a directory."""
    import fnmatch
    root = resolve(path)
    skip = {".git", "node_modules", "__pycache__", "venv", "dist", ".venv"}
    changed = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            if glob and not fnmatch.fnmatch(fn, glob):
                continue
            fp = os.path.join(dirpath, fn)
            if not _is_text_file(fp):
                continue
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    data = f.read()
                if find in data:
                    with open(fp, "w", encoding="utf-8") as f:
                        f.write(data.replace(find, replace))
                    changed.append(rel(fp))
            except Exception:
                continue
    if not changed:
        return f"No files contained '{find}'."
    return f"Updated {len(changed)} file(s):\n" + "\n".join(changed[:60])


def glob_files(pattern: str, path: str = ".") -> str:
    """Find files matching a glob pattern (e.g. '**/*.py', 'src/*.tsx')."""
    import glob as _glob
    root = resolve(path)
    if not os.path.isdir(root):
        return f"Error: not a directory: {rel(root)}"
    pat = os.path.join(root, pattern)
    skip = ("/node_modules/", "/.git/", "/__pycache__/", "/venv/", "/dist/", "/.venv/")
    hits = [m for m in _glob.glob(pat, recursive=True)
            if not any(s in (m + "/") for s in skip)]
    hits = sorted(hits)
    if not hits:
        return f"No files match '{pattern}' under {rel(root)}/"
    out = "\n".join(rel(m) + ("/" if os.path.isdir(m) else "") for m in hits[:300])
    return f"{len(hits)} match(es) for '{pattern}':\n" + out + ("\n[...truncated]" if len(hits) > 300 else "")


_GREP_SKIP = (".git", "node_modules", "__pycache__", "venv", ".venv", "dist", ".next")


def _grep_ripgrep(pattern: str, root: str, glob: str = "") -> str | None:
    """Fast path: shell out to ripgrep when it's installed (10–100× faster on
    large codebases). Returns the formatted result, or None to fall back to the
    pure-Python walk (rg missing, or rg reported an internal error)."""
    import shutil as _sh
    import subprocess as _sp
    from tools.sandbox import get_workspace
    rg = _sh.which("rg")
    if not rg:
        return None
    sub = rel(root) or "."
    cmd = [rg, "-n", "--no-heading", "--color=never"]
    for ex in _GREP_SKIP:
        cmd += ["-g", f"!{ex}"]
    if glob:
        cmd += ["-g", glob]
    cmd += ["-e", pattern, "--", sub]
    try:
        proc = _sp.run(cmd, cwd=get_workspace(), capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    if proc.returncode == 1:                      # ran fine, zero matches
        return f"No matches for /{pattern}/ under {sub}/"
    if proc.returncode != 0:                       # rg errored → use Python path
        return None
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    if not lines:
        return f"No matches for /{pattern}/ under {sub}/"
    body = "\n".join(ln[:240] for ln in lines[:200])
    if len(lines) > 200:
        body += "\n[...more matches truncated]"
    return body


def grep(pattern: str, path: str = ".", glob: str = "") -> str:
    """Regex search file contents across the workspace (ripgrep-style)."""
    import re as _re
    import fnmatch
    try:
        rx = _re.compile(pattern)
    except _re.error as e:
        return f"Error: invalid regex: {e}"
    root = resolve(path)
    rg_result = _grep_ripgrep(pattern, root, glob)
    if rg_result is not None:
        return rg_result
    skip = {".git", "node_modules", "__pycache__", "venv", "dist", ".venv", ".next"}
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            if glob and not fnmatch.fnmatch(fn, glob):
                continue
            fp = os.path.join(dirpath, fn)
            if not _is_text_file(fp):
                continue
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if rx.search(line):
                            hits.append(f"{rel(fp)}:{i}: {line.strip()[:200]}")
                            if len(hits) >= 200:
                                raise StopIteration
            except StopIteration:
                return "\n".join(hits) + "\n[...more matches truncated]"
            except Exception:
                continue
    if not hits:
        return f"No matches for /{pattern}/ under {rel(root)}/"
    return "\n".join(hits)


def tree_directory(path: str = ".", max_depth: int = 4) -> str:
    """Recursive tree view of directory structure."""
    root = resolve(path)
    if not os.path.isdir(root):
        return f"Error: not a directory: {rel(root)}"
    skip = {".git", "node_modules", "__pycache__", "venv", "dist", ".venv", ".next"}
    lines = [f"{rel(root)}/"]
    def _walk(dir_path, prefix, depth):
        if depth > max_depth:
            return
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return
        dirs = [e for e in entries if os.path.isdir(os.path.join(dir_path, e)) and e not in skip]
        files = [e for e in entries if os.path.isfile(os.path.join(dir_path, e))]
        all_items = [(d, True) for d in dirs] + [(f, False) for f in files]
        for i, (name, is_dir) in enumerate(all_items):
            is_last = i == len(all_items) - 1
            connector = "└── " if is_last else "├── "
            if is_dir:
                lines.append(f"{prefix}{connector}{name}/")
                extension = "    " if is_last else "│   "
                _walk(os.path.join(dir_path, name), prefix + extension, depth + 1)
            else:
                try:
                    size = os.path.getsize(os.path.join(dir_path, name))
                except Exception:
                    size = 0
                lines.append(f"{prefix}{connector}{name} ({size}b)")
    _walk(root, "", 1)
    return "\n".join(lines[:500]) + ("\n[...truncated]" if len(lines) > 500 else "")


def batch_read_files(paths: list) -> str:
    """Read multiple files in one call. Returns concatenated contents."""
    if isinstance(paths, str):
        paths = [p.strip() for p in paths.split(",") if p.strip()]
    results = []
    for p in paths[:20]:  # limit to 20 files
        content = read_file(p)
        results.append(f"=== {p} ===\n{content}")
    return "\n\n".join(results)


def batch_write_files(files: list) -> str:
    """Write multiple files in one call. Each item: {path, content}."""
    if not files or not isinstance(files, list):
        return "Error: provide a list of {path, content} objects."
    results = []
    for item in files[:20]:  # limit to 20 files
        if isinstance(item, dict):
            path = item.get("path", "")
            content = item.get("content", "")
            result = write_file(path, content)
            results.append(result)
    return "\n".join(results) if results else "No files written."


def patch_file(path: str, patches: list) -> str:
    """Apply multiple find/replace patches to a file in one call.
    patches: list of {find: str, replace: str}
    """
    p = resolve(path)
    if not os.path.isfile(p):
        return f"Error: file not found: {rel(p)}"
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
        count = 0
        for patch in (patches or []):
            if isinstance(patch, dict):
                find = patch.get("find", "")
                replace = patch.get("replace", "")
                if find and find in data:
                    data = data.replace(find, replace)
                    count += 1
        with open(p, "w", encoding="utf-8") as f:
            f.write(data)
        return f"Applied {count} patch(es) to {rel(p)}"
    except Exception as e:
        return f"Error patching {rel(p)}: {e}"


def apply_patch(diff: str) -> str:
    """Apply a unified diff (git/`diff -u` format) to the workspace, like Codex.
    Supports creating, editing, renaming and deleting files in one shot."""
    import subprocess, tempfile
    from tools.sandbox import get_workspace
    if not diff or not diff.strip():
        return "Error: empty patch."
    ws = get_workspace()
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".patch", dir=ws, delete=False,
                                         encoding="utf-8") as tf:
            tf.write(diff if diff.endswith("\n") else diff + "\n")
            patch_path = tf.name
        # Try a few strip levels; git apply works outside a repo too.
        last_err = ""
        for args in (["git", "apply", "--whitespace=nofix", patch_path],
                     ["git", "apply", "-p0", "--whitespace=nofix", patch_path],
                     ["patch", "-p1", "-i", patch_path],
                     ["patch", "-p0", "-i", patch_path]):
            try:
                proc = subprocess.run(args, cwd=ws, capture_output=True, text=True, timeout=30)
            except FileNotFoundError:
                continue
            if proc.returncode == 0:
                try:
                    os.remove(patch_path)
                except OSError:
                    pass
                return "Patch applied successfully."
            last_err = (proc.stderr or proc.stdout or "").strip()
        try:
            os.remove(patch_path)
        except OSError:
            pass
        return f"Error applying patch: {last_err[:1500]}"
    except Exception as e:
        return f"Error applying patch: {e}"


def compare_files(path_a: str, path_b: str) -> str:
    """Compare two files and show differences."""
    a = resolve(path_a)
    b = resolve(path_b)
    if not os.path.isfile(a):
        return f"Error: file not found: {rel(a)}"
    if not os.path.isfile(b):
        return f"Error: file not found: {rel(b)}"
    try:
        import difflib
        with open(a, "r", encoding="utf-8", errors="replace") as fa:
            lines_a = fa.readlines()
        with open(b, "r", encoding="utf-8", errors="replace") as fb:
            lines_b = fb.readlines()
        diff = list(difflib.unified_diff(lines_a, lines_b,
                                          fromfile=rel(a), tofile=rel(b), lineterm=""))
        if not diff:
            return f"Files are identical: {rel(a)} and {rel(b)}"
        return "\n".join(diff[:300]) + ("\n[...truncated]" if len(diff) > 300 else "")
    except Exception as e:
        return f"Error comparing files: {e}"
