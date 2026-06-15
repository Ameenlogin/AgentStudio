"""Archive tools: create, extract and inspect .zip / .tar archives, sandboxed."""
import os
import zipfile
import tarfile
from tools.sandbox import resolve, rel


def create_zip(output: str, paths) -> str:
    out = resolve(output)
    if isinstance(paths, str):
        paths = [p.strip() for p in paths.split(",") if p.strip()]
    if not paths:
        return "Error: provide one or more paths to add to the archive."
    try:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        n = 0
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in paths:
                full = resolve(p)
                if os.path.isdir(full):
                    for dp, _, files in os.walk(full):
                        for fn in files:
                            fp = os.path.join(dp, fn)
                            zf.write(fp, os.path.relpath(fp, os.path.dirname(full)))
                            n += 1
                elif os.path.isfile(full):
                    zf.write(full, os.path.basename(full))
                    n += 1
        return f"Created {rel(out)} with {n} file(s)."
    except Exception as e:
        return f"Error creating zip: {e}"


def extract_zip(path: str, dest: str = ".") -> str:
    src = resolve(path)
    out = resolve(dest)
    if not os.path.isfile(src):
        return f"Error: archive not found: {rel(src)}"
    try:
        os.makedirs(out, exist_ok=True)
        names = []
        if zipfile.is_zipfile(src):
            with zipfile.ZipFile(src) as zf:
                for member in zf.namelist():
                    # Block path traversal inside the archive.
                    target = os.path.normpath(os.path.join(out, member))
                    if not target.startswith(os.path.normpath(out)):
                        return f"Error: archive entry escapes destination: {member}"
                zf.extractall(out)
                names = zf.namelist()
        elif tarfile.is_tarfile(src):
            with tarfile.open(src) as tf:
                tf.extractall(out)
                names = tf.getnames()
        else:
            return "Error: not a recognized zip or tar archive."
        return f"Extracted {len(names)} item(s) to {rel(out)}/\n" + "\n".join(names[:40]) + ("\n[...]" if len(names) > 40 else "")
    except Exception as e:
        return f"Error extracting archive: {e}"


def zip_read(path: str, inner: str) -> str:
    """Read one file's text content from inside a .zip without extracting it."""
    src = resolve(path)
    if not os.path.isfile(src) or not zipfile.is_zipfile(src):
        return f"Error: not a zip archive: {rel(src)}"
    try:
        with zipfile.ZipFile(src) as zf:
            if inner not in zf.namelist():
                return f"Error: '{inner}' not in archive. Use list_archive to see entries."
            data = zf.read(inner)
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return f"[binary file, {len(data)} bytes]"
    except Exception as e:
        return f"Error reading from zip: {e}"


def _rewrite_zip(src: str, mutate) -> str:
    """Rewrite a zip applying mutate(entries) where entries is a dict
    {name: bytes}. Returns a status string."""
    import io
    existing: dict[str, bytes] = {}
    if os.path.isfile(src) and zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as zf:
            for n in zf.namelist():
                existing[n] = zf.read(n)
    mutate(existing)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for n, data in existing.items():
            zf.writestr(n, data)
    with open(src, "wb") as f:
        f.write(buf.getvalue())
    return f"{rel(src)} now has {len(existing)} entries."


def zip_write(path: str, inner: str, content: str) -> str:
    """Add or replace a text file *inside* a .zip in place (creates the zip if
    missing). Use this to write code directly into an archive."""
    src = resolve(path)
    try:
        os.makedirs(os.path.dirname(src) or ".", exist_ok=True)
        existed = inner in (zipfile.ZipFile(src).namelist()
                            if os.path.isfile(src) and zipfile.is_zipfile(src) else [])
        msg = _rewrite_zip(src, lambda e: e.__setitem__(inner, (content or "").encode("utf-8")))
        verb = "Updated" if existed else "Added"
        return f"{verb} '{inner}' in {rel(src)}. {msg}"
    except Exception as e:
        return f"Error writing into zip: {e}"


def zip_edit(path: str, inner: str, find: str, replace: str) -> str:
    """Find-and-replace inside a single text file within a .zip, in place."""
    src = resolve(path)
    if not os.path.isfile(src) or not zipfile.is_zipfile(src):
        return f"Error: not a zip archive: {rel(src)}"
    try:
        with zipfile.ZipFile(src) as zf:
            if inner not in zf.namelist():
                return f"Error: '{inner}' not in archive."
            data = zf.read(inner).decode("utf-8", errors="replace")
        if find not in data:
            return f"Error: 'find' text not found in {inner}."
        count = data.count(find)
        new = data.replace(find, replace)
        _rewrite_zip(src, lambda e: e.__setitem__(inner, new.encode("utf-8")))
        return f"Replaced {count} occurrence(s) in '{inner}' inside {rel(src)}."
    except Exception as e:
        return f"Error editing inside zip: {e}"


def zip_remove(path: str, inner: str) -> str:
    """Remove a file entry from inside a .zip in place."""
    src = resolve(path)
    if not os.path.isfile(src) or not zipfile.is_zipfile(src):
        return f"Error: not a zip archive: {rel(src)}"
    try:
        with zipfile.ZipFile(src) as zf:
            if inner not in zf.namelist():
                return f"Error: '{inner}' not in archive."
        _rewrite_zip(src, lambda e: e.pop(inner, None))
        return f"Removed '{inner}' from {rel(src)}."
    except Exception as e:
        return f"Error removing from zip: {e}"


def list_archive(path: str) -> str:
    src = resolve(path)
    if not os.path.isfile(src):
        return f"Error: archive not found: {rel(src)}"
    try:
        if zipfile.is_zipfile(src):
            with zipfile.ZipFile(src) as zf:
                info = zf.infolist()
                lines = [f"{i.file_size:>10}  {i.filename}" for i in info[:200]]
                return f"{rel(src)} — {len(info)} entries:\n" + "\n".join(lines)
        if tarfile.is_tarfile(src):
            with tarfile.open(src) as tf:
                names = tf.getnames()
                return f"{rel(src)} — {len(names)} entries:\n" + "\n".join(names[:200])
        return "Error: not a recognized zip or tar archive."
    except Exception as e:
        return f"Error reading archive: {e}"
