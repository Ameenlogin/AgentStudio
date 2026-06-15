"""Central tool registry: JSON schemas sent to the model + a dispatcher.

The toolkit is intentionally broad so the agent can plan, build, test, fetch,
scrape, archive and ship work end to end with minimal hand-holding.
"""
from tools.file_tools import (
    read_file, write_file, edit_file, list_directory, create_directory, search_files,
    append_file, delete_path, move_path, copy_path, file_info, replace_in_files,
    tree_directory, batch_read_files, batch_write_files, patch_file, compare_files,
    apply_patch, glob_files, grep,
)
from tools.git_tools import git_status, git_diff, git_log, git_commit
from tools.shell_tools import run_command, run_command_stream
from tools.process_tools import start_process, read_process, stop_process, list_processes
from tools.web_tools import (
    web_search, fetch_url, scrape, extract_links, http_request, download_file,
)
from tools.archive_tools import (
    create_zip, extract_zip, list_archive, zip_read, zip_write, zip_edit, zip_remove,
)
from tools.pdf_tools import pdf_read, pdf_info, pdf_create
from tools.data_tools import python_exec, python_exec_stream, install_package
from services import skills as _skills


def _fn(name, description, properties, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


_S = {"type": "string"}

AVAILABLE_TOOLS = [
    # ── Files ────────────────────────────────────────────────────────────────
    _fn("read_file", "Read a text file in the workspace. For LARGE files, pass offset (1-based start line) and/or limit (line count) to page through any range without loading the whole file.",
        {"path": {"type": "string", "description": "File path relative to the workspace."},
         "offset": {"type": "integer", "description": "Optional 1-based line to start at (for large files)."},
         "limit": {"type": "integer", "description": "Optional number of lines to read from offset."}}, ["path"]),
    _fn("write_file", "Create or overwrite a file with the given content.",
        {"path": _S, "content": {"type": "string", "description": "Full file content."}}, ["path", "content"]),
    _fn("append_file", "Append text to the end of a file (creating it if needed).",
        {"path": _S, "content": _S}, ["path", "content"]),
    _fn("edit_file", "Replace an exact text snippet inside an existing file.",
        {"path": _S, "find": {"type": "string", "description": "Exact text to find."},
         "replace": {"type": "string", "description": "Replacement text."}}, ["path", "find", "replace"]),
    _fn("replace_in_files", "Find-and-replace a string across many files under a directory.",
        {"find": _S, "replace": _S, "path": {"type": "string", "description": "Root dir (default '.')."},
         "glob": {"type": "string", "description": "Optional filename glob, e.g. '*.py'."}}, ["find", "replace"]),
    _fn("list_directory", "List files and folders in a workspace directory.",
        {"path": {"type": "string", "description": "Directory path (default '.')."}}, []),
    _fn("create_directory", "Create a new directory (and parents).", {"path": _S}, ["path"]),
    _fn("delete_path", "Delete a file or directory in the workspace.", {"path": _S}, ["path"]),
    _fn("move_path", "Move or rename a file or directory.", {"src": _S, "dest": _S}, ["src", "dest"]),
    _fn("copy_path", "Copy a file or directory.", {"src": _S, "dest": _S}, ["src", "dest"]),
    _fn("file_info", "Get type, size and modified time of a path.", {"path": _S}, ["path"]),
    _fn("search_files", "Search file contents for a text string across the workspace.",
        {"query": _S, "path": {"type": "string", "description": "Root dir (default '.')."}}, ["query"]),
    _fn("grep", "Regex search file contents across the workspace (ripgrep-style). Faster, more precise than search_files.",
        {"pattern": {"type": "string", "description": "Regular expression."},
         "path": {"type": "string", "description": "Root dir (default '.')."},
         "glob": {"type": "string", "description": "Optional filename glob, e.g. '*.py'."}}, ["pattern"]),
    _fn("glob_files", "Find files by glob pattern (e.g. '**/*.py', 'src/*.tsx').",
        {"pattern": _S, "path": {"type": "string", "description": "Root dir (default '.')."}}, ["pattern"]),
    # ── Shell + code ───────────────────────────────────────────────────────────
    _fn("run_command", "Run a shell command inside the workspace and return its output.",
        {"command": _S}, ["command"]),
    _fn("python_exec", "Execute a Python snippet in the workspace and return stdout/stderr.",
        {"code": {"type": "string", "description": "Python source to run."}}, ["code"]),
    _fn("install_package", "pip-install Python package(s) into the app environment so you can use them (e.g. lxml, pandas, pillow, playwright). Use when a needed library is missing.",
        {"package": {"type": "string", "description": "Package spec, e.g. 'pandas' or 'lxml beautifulsoup4'."}}, ["package"]),
    _fn("start_process", "Start a LONG-RUNNING command in the background (dev server, watcher, `npm run dev`, `python -m http.server`) without blocking. Returns a handle and the first lines of output. Use this instead of run_command for anything that does not exit on its own.",
        {"command": {"type": "string", "description": "The command to launch, e.g. 'npm run dev' or 'python app.py'."}}, ["command"]),
    _fn("read_process", "Read the latest output and status (running/exited) of a background process started with start_process.",
        {"id": {"type": "string", "description": "Process handle, e.g. 'proc1'."},
         "lines": {"type": "integer", "description": "How many recent lines to return (default 80)."}}, ["id"]),
    _fn("stop_process", "Stop a background process started with start_process (terminates its whole process group).",
        {"id": {"type": "string", "description": "Process handle, e.g. 'proc1'."}}, ["id"]),
    _fn("list_processes", "List background processes started this session and whether each is still running.", {}, []),
    # ── Web + scraping ─────────────────────────────────────────────────────────
    _fn("web_search", "Search the web and return the top results.", {"query": _S}, ["query"]),
    _fn("fetch_url", "Fetch a web page and return its readable text.", {"url": _S}, ["url"]),
    _fn("scrape", "Fetch a page and extract elements by CSS selector (text, or an attribute).",
        {"url": _S, "selector": {"type": "string", "description": "CSS selector, e.g. 'h2.title'."},
         "attr": {"type": "string", "description": "Optional attribute to read, e.g. 'href'."}}, ["url"]),
    _fn("extract_links", "Return all hyperlinks found on a page.", {"url": _S}, ["url"]),
    _fn("http_request", "Make an HTTP request (GET/POST/PUT/DELETE) with optional headers/body.",
        {"url": _S, "method": {"type": "string", "description": "HTTP method (default GET)."},
         "headers": {"type": "object", "description": "Optional request headers."},
         "body": {"type": "string", "description": "Optional raw body."},
         "json_body": {"type": "object", "description": "Optional JSON body."}}, ["url"]),
    _fn("download_file", "Download a file from a URL into the workspace.",
        {"url": _S, "dest": {"type": "string", "description": "Optional destination filename."}}, ["url"]),
    # ── Archives ───────────────────────────────────────────────────────────────
    _fn("create_zip", "Create a .zip archive from one or more workspace paths.",
        {"output": {"type": "string", "description": "Output .zip path."},
         "paths": {"type": "array", "items": {"type": "string"}, "description": "Files/folders to include."}},
        ["output", "paths"]),
    _fn("extract_zip", "Extract a .zip or .tar archive into the workspace.",
        {"path": _S, "dest": {"type": "string", "description": "Destination dir (default '.')."}}, ["path"]),
    _fn("list_archive", "List the contents of a .zip or .tar archive.", {"path": _S}, ["path"]),
    # ── Files (new) ─────────────────────────────────────────────────────────
    _fn("tree_directory", "Show a recursive tree view of a directory structure.",
        {"path": {"type": "string", "description": "Root directory (default '.')."},
         "max_depth": {"type": "integer", "description": "Max depth (default 4)."}}, []),
    _fn("batch_read_files", "Read multiple files in one call, saving API round-trips.",
        {"paths": {"type": "array", "items": {"type": "string"}, "description": "List of file paths."}}, ["paths"]),
    _fn("batch_write_files", "Write multiple files in one call.",
        {"files": {"type": "array", "items": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}, "description": "List of {path, content} objects."}}, ["files"]),
    _fn("patch_file", "Apply multiple find/replace patches to a file in one call.",
        {"path": _S, "patches": {"type": "array", "items": {"type": "object", "properties": {"find": {"type": "string"}, "replace": {"type": "string"}}}, "description": "List of {find, replace} patches."}}, ["path", "patches"]),
    _fn("compare_files", "Compare two files and show a unified diff.",
        {"path_a": _S, "path_b": _S}, ["path_a", "path_b"]),
    _fn("apply_patch", "Apply a unified diff (git/`diff -u` format) to the workspace — "
        "create, edit, rename or delete files in one shot. The most precise way to edit code.",
        {"diff": {"type": "string", "description": "A unified diff patch."}}, ["diff"]),
    # ── Zip editing (in place) ──────────────────────────────────────────────
    _fn("zip_read", "Read one file's text from inside a .zip without extracting it.",
        {"path": _S, "inner": {"type": "string", "description": "Path of the file inside the archive."}}, ["path", "inner"]),
    _fn("zip_write", "Write/replace a text file directly INSIDE a .zip in place (creates the zip if missing). "
        "Use to push code into an archive without unzipping.",
        {"path": _S, "inner": _S, "content": _S}, ["path", "inner", "content"]),
    _fn("zip_edit", "Find-and-replace inside a single text file within a .zip, in place.",
        {"path": _S, "inner": _S, "find": _S, "replace": _S}, ["path", "inner", "find", "replace"]),
    _fn("zip_remove", "Remove a file entry from inside a .zip in place.",
        {"path": _S, "inner": _S}, ["path", "inner"]),
    # ── PDF ─────────────────────────────────────────────────────────────────
    _fn("pdf_read", "Extract the text from a PDF file.", {"path": _S}, ["path"]),
    _fn("pdf_info", "Report page count and metadata for a PDF.", {"path": _S}, ["path"]),
    _fn("pdf_create", "Create a PDF from plain text or light Markdown (#, ##, - bullets).",
        {"path": _S, "content": _S, "title": {"type": "string", "description": "Optional document title."}}, ["path", "content"]),
    # ── Skills ──────────────────────────────────────────────────────────────
    _fn("list_skills", "List installed skills (reusable expertise packs) and their descriptions.", {}, []),
    _fn("read_skill", "Read a skill's full guide before doing a matching task.",
        {"name": {"type": "string", "description": "Skill name from list_skills."}}, ["name"]),
    _fn("install_skill", "Install a skill from a public GitHub/GitLab repo URL, then follow its SKILL.md/README.",
        {"url": {"type": "string", "description": "Repo URL, e.g. https://github.com/owner/repo"}}, ["url"]),
    # ── Git ─────────────────────────────────────────────────────────────────
    _fn("git_status", "Show the current git status (changed/staged files).", {}, []),
    _fn("git_diff", "Show git diff for the workspace or a specific file.",
        {"path": {"type": "string", "description": "Optional file path to diff."}}, []),
    _fn("git_log", "Show recent git commit history.",
        {"n": {"type": "integer", "description": "Number of commits (default 10)."}}, []),
    _fn("git_commit", "Stage all changes and commit with a message.",
        {"message": _S}, ["message"]),
]

_DISPATCH = {
    "read_file":        lambda a: read_file(a.get("path", ""), a.get("offset", 0), a.get("limit", 0)),
    "write_file":       lambda a: write_file(a.get("path", ""), a.get("content", "")),
    "append_file":      lambda a: append_file(a.get("path", ""), a.get("content", "")),
    "edit_file":        lambda a: edit_file(a.get("path", ""), a.get("find", ""), a.get("replace", "")),
    "replace_in_files": lambda a: replace_in_files(a.get("find", ""), a.get("replace", ""), a.get("path", "."), a.get("glob", "")),
    "list_directory":   lambda a: list_directory(a.get("path", ".")),
    "create_directory": lambda a: create_directory(a.get("path", "")),
    "delete_path":      lambda a: delete_path(a.get("path", "")),
    "move_path":        lambda a: move_path(a.get("src", ""), a.get("dest", "")),
    "copy_path":        lambda a: copy_path(a.get("src", ""), a.get("dest", "")),
    "file_info":        lambda a: file_info(a.get("path", "")),
    "search_files":     lambda a: search_files(a.get("query", ""), a.get("path", ".")),
    "grep":             lambda a: grep(a.get("pattern", ""), a.get("path", "."), a.get("glob", "")),
    "glob_files":       lambda a: glob_files(a.get("pattern", ""), a.get("path", ".")),
    "run_command":      lambda a: run_command(a.get("command", "")),
    "python_exec":      lambda a: python_exec(a.get("code", "")),
    "install_package":  lambda a: install_package(a.get("package", "")),
    "start_process":    lambda a: start_process(a.get("command", "")),
    "read_process":     lambda a: read_process(a.get("id", ""), a.get("lines", 80)),
    "stop_process":     lambda a: stop_process(a.get("id", "")),
    "list_processes":   lambda a: list_processes(),
    "web_search":       lambda a: web_search(a.get("query", "")),
    "fetch_url":        lambda a: fetch_url(a.get("url", "")),
    "scrape":           lambda a: scrape(a.get("url", ""), a.get("selector", ""), a.get("attr", "")),
    "extract_links":    lambda a: extract_links(a.get("url", "")),
    "http_request":     lambda a: http_request(a.get("url", ""), a.get("method", "GET"), a.get("headers"), a.get("body", ""), a.get("json_body")),
    "download_file":    lambda a: download_file(a.get("url", ""), a.get("dest", "")),
    "create_zip":       lambda a: create_zip(a.get("output", ""), a.get("paths", [])),
    "extract_zip":      lambda a: extract_zip(a.get("path", ""), a.get("dest", ".")),
    "list_archive":     lambda a: list_archive(a.get("path", "")),
    "tree_directory":   lambda a: tree_directory(a.get("path", "."), a.get("max_depth", 4)),
    "batch_read_files": lambda a: batch_read_files(a.get("paths", [])),
    "batch_write_files":lambda a: batch_write_files(a.get("files", [])),
    "patch_file":       lambda a: patch_file(a.get("path", ""), a.get("patches", [])),
    "compare_files":    lambda a: compare_files(a.get("path_a", ""), a.get("path_b", "")),
    "apply_patch":      lambda a: apply_patch(a.get("diff", "")),
    "zip_read":         lambda a: zip_read(a.get("path", ""), a.get("inner", "")),
    "zip_write":        lambda a: zip_write(a.get("path", ""), a.get("inner", ""), a.get("content", "")),
    "zip_edit":         lambda a: zip_edit(a.get("path", ""), a.get("inner", ""), a.get("find", ""), a.get("replace", "")),
    "zip_remove":       lambda a: zip_remove(a.get("path", ""), a.get("inner", "")),
    "pdf_read":         lambda a: pdf_read(a.get("path", "")),
    "pdf_info":         lambda a: pdf_info(a.get("path", "")),
    "pdf_create":       lambda a: pdf_create(a.get("path", ""), a.get("content", ""), a.get("title", "")),
    "list_skills":      lambda a: "\n".join(f"- {s['name']}: {s['description']}" for s in _skills.list_skills()) or "No skills installed.",
    "read_skill":       lambda a: _skills.read_skill(a.get("name", "")),
    "install_skill":    lambda a: _skills.install_from_github(a.get("url", "")),
    "git_status":       lambda a: git_status(),
    "git_diff":         lambda a: git_diff(a.get("path", "")),
    "git_log":          lambda a: git_log(a.get("n", 10)),
    "git_commit":       lambda a: git_commit(a.get("message", "auto commit")),
}

# UI hints: icon + accent "kind" per tool. kind drives both color and whether
# the action needs permission in "ask" mode (write/shell/system are gated).
TOOL_META = {
    "read_file":        {"label": "Read file",        "icon": "file-text",    "kind": "read"},
    "write_file":       {"label": "Write file",       "icon": "file-plus",    "kind": "write"},
    "append_file":      {"label": "Append to file",   "icon": "file-pen",     "kind": "write"},
    "edit_file":        {"label": "Edit file",        "icon": "file-pen",     "kind": "write"},
    "replace_in_files": {"label": "Replace in files", "icon": "file-pen",     "kind": "write"},
    "list_directory":   {"label": "List directory",   "icon": "folder",       "kind": "read"},
    "create_directory": {"label": "Create directory", "icon": "folder-plus",  "kind": "write"},
    "delete_path":      {"label": "Delete path",      "icon": "trash",        "kind": "write"},
    "move_path":        {"label": "Move / rename",    "icon": "file-pen",     "kind": "write"},
    "copy_path":        {"label": "Copy path",        "icon": "copy",         "kind": "write"},
    "file_info":        {"label": "File info",        "icon": "file-text",    "kind": "read"},
    "search_files":     {"label": "Search files",     "icon": "search",       "kind": "read"},
    "grep":             {"label": "Grep",             "icon": "search",       "kind": "read"},
    "glob_files":       {"label": "Find files",       "icon": "search",       "kind": "read"},
    "run_command":      {"label": "Run command",      "icon": "terminal",     "kind": "shell"},
    "python_exec":      {"label": "Run Python",       "icon": "terminal",     "kind": "shell"},
    "install_package":  {"label": "Install package",  "icon": "download",     "kind": "shell"},
    "start_process":    {"label": "Start process",    "icon": "terminal",     "kind": "shell"},
    "read_process":     {"label": "Read process",     "icon": "terminal",     "kind": "read"},
    "stop_process":     {"label": "Stop process",     "icon": "terminal",     "kind": "shell"},
    "list_processes":   {"label": "List processes",   "icon": "terminal",     "kind": "read"},
    "web_search":       {"label": "Web search",       "icon": "globe",        "kind": "web"},
    "fetch_url":        {"label": "Fetch page",       "icon": "link",         "kind": "web"},
    "scrape":           {"label": "Scrape page",      "icon": "globe",        "kind": "web"},
    "extract_links":    {"label": "Extract links",    "icon": "link",         "kind": "web"},
    "http_request":     {"label": "HTTP request",     "icon": "globe",        "kind": "web"},
    "download_file":    {"label": "Download file",    "icon": "download",     "kind": "web"},
    "create_zip":       {"label": "Create archive",   "icon": "archive",      "kind": "write"},
    "extract_zip":      {"label": "Extract archive",  "icon": "archive",      "kind": "write"},
    "list_archive":     {"label": "List archive",     "icon": "archive",      "kind": "read"},
    "tree_directory":   {"label": "Directory tree",   "icon": "folder-tree", "kind": "read"},
    "batch_read_files": {"label": "Batch read",       "icon": "files",       "kind": "read"},
    "batch_write_files":{"label": "Batch write",      "icon": "files",       "kind": "write"},
    "patch_file":       {"label": "Patch file",       "icon": "file-pen",    "kind": "write"},
    "compare_files":    {"label": "Compare files",    "icon": "diff",        "kind": "read"},
    "apply_patch":      {"label": "Apply patch",      "icon": "diff",        "kind": "write"},
    "zip_read":         {"label": "Read in archive",  "icon": "archive",     "kind": "read"},
    "zip_write":        {"label": "Write in archive", "icon": "archive",     "kind": "write"},
    "zip_edit":         {"label": "Edit in archive",  "icon": "archive",     "kind": "write"},
    "zip_remove":       {"label": "Remove in archive","icon": "archive",     "kind": "write"},
    "pdf_read":         {"label": "Read PDF",         "icon": "file-text",   "kind": "read"},
    "pdf_info":         {"label": "PDF info",         "icon": "file-text",   "kind": "read"},
    "pdf_create":       {"label": "Create PDF",       "icon": "file-plus",   "kind": "write"},
    "list_skills":      {"label": "List skills",      "icon": "list-checks", "kind": "read"},
    "read_skill":       {"label": "Read skill",       "icon": "file-text",   "kind": "read"},
    "install_skill":    {"label": "Install skill",    "icon": "download",    "kind": "web"},
    "git_status":       {"label": "Git status",       "icon": "git-branch",  "kind": "read"},
    "git_diff":         {"label": "Git diff",         "icon": "git-branch",  "kind": "read"},
    "git_log":          {"label": "Git log",          "icon": "git-branch",  "kind": "read"},
    "git_commit":       {"label": "Git commit",       "icon": "git-branch",  "kind": "write"},
}

# Which tool kinds require user approval when permission_mode == "ask".
RISKY_KINDS = {"write", "shell", "system"}

# Read-only tool kinds are side-effect-free and therefore safe to run
# concurrently when the model requests several in a single turn.
READ_KINDS = {"read", "web"}

# Tools that can stream their output line-by-line in real time.
STREAMING_DISPATCH = {
    "run_command": lambda a, on_line: run_command_stream(a.get("command", ""), on_line),
    "python_exec": lambda a, on_line: python_exec_stream(a.get("code", ""), on_line),
}


def is_parallel_safe(name: str) -> bool:
    """A tool is safe to run in parallel only if it is purely read-only."""
    return TOOL_META.get(name, {}).get("kind") in READ_KINDS


def execute_tool(name: str, arguments: dict) -> str:
    fn = _DISPATCH.get(name)
    if not fn:
        return f"Unknown tool: {name}"
    try:
        return fn(arguments or {})
    except PermissionError as e:
        return f"Blocked: {e}"
    except Exception as e:
        return f"Error executing {name}: {e}"


def execute_tool_streaming(name: str, arguments: dict, on_line) -> str:
    """Execute a streaming-capable tool, pushing incremental output through
    on_line(text). Falls back to the blocking executor for other tools."""
    fn = STREAMING_DISPATCH.get(name)
    if not fn:
        return execute_tool(name, arguments)
    try:
        return fn(arguments or {}, on_line)
    except PermissionError as e:
        return f"Blocked: {e}"
    except Exception as e:
        return f"Error executing {name}: {e}"
