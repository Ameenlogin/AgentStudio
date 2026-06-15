# Agent Studio

A local, Claude-Code–style autonomous engineering agent with a live
"thinking + tool execution" timeline. It runs entirely on your Mac and talks to
Moonshot's **Kimi K2** models through **NVIDIA NIM** (free API key).

![status](https://img.shields.io/badge/status-ready-brightgreen)
![platform](https://img.shields.io/badge/platform-macOS-black)

---

## Quick start (macOS)

Double-click **`START.command`** in Finder. The first run sets up anything missing
(Python virtual environment + packages), then starts the app and opens it in your
browser at <http://127.0.0.1:8000>. The UI ships prebuilt, so a normal first run
needs only **Python 3.10+** — no Node.js required.

- **First time only**, if double-click is blocked, open Terminal in this folder and run:
  ```bash
  chmod +x *.command
  xattr -dr com.apple.quarantine .
  ```
  (Or right-click `START.command` → **Open** the first time.)
- To **stop**: press `Ctrl+C` in the Terminal window, or close it.
- `install.command` (full setup incl. Node build) and `run.command` (start only)
  are also provided, but `START.command` alone is all you need.

> No Python? `brew install python` or grab it from python.org.

This is a macOS build — the Windows `.bat` launchers have been removed.

---

## What it does

Agent Studio is an **agentic** assistant, not just a chatbot. Give it a task and it
plans, calls real tools on your machine, sees the results, and keeps going until the
job is done — all streamed live so you can watch it think and act.

### Capabilities

| Group | What it can do |
|-------|----------------|
| **Files** | read / write / append / edit / move / copy / delete, batch read & write, recursive tree, search & bulk-replace, precise unified-diff `apply_patch` |
| **Archives** | create / extract / list zips **and edit files in place inside a zip** (`zip_read` / `zip_write` / `zip_edit` / `zip_remove`) |
| **PDFs** | extract text, inspect, and **create PDFs** from text/Markdown |
| **Code** | run shell commands and Python with **live streamed stdout/stderr**; git status/diff/log/commit |
| **Web** | search, fetch readable text, scrape by CSS selector, extract links, HTTP requests, downloads |

It can build complete **websites & web apps**, **WordPress themes/plugins (PHP)**,
CLIs, scripts, data pipelines, design assets, documents and PDFs — and package the
result into a downloadable zip.

---

## The engine (what's under the hood)

- **Two-speed router** — trivial / conversational messages get one fast streamed
  reply; anything that needs to act runs the full plan→act→observe tool loop.
- **Multi-agent swarm** *(auto, for complex tasks)* —
  `Planner → parallel research workers → Builder → Synthesizer`. Independent research
  runs concurrently; the builder writes code with your permission gate active.
- **Parallel tool execution** — independent read-only tool calls in a turn run at once.
- **Live tool streaming** — shell/Python output streams to the UI line-by-line.
- **API-key health rotation** — requests spread across your NIM keys, each held under
  ~38 RPM via a sliding window; flaky/limited keys are rotated out automatically.
- **Streaming circuit breaker** — a stalled stream (no chunk for 5s before output)
  is cut and retried on an alternate key/endpoint.
- **Semantic response cache** — near-identical questions are answered instantly from a
  local embedding cache (zero extra API calls — it protects your rate budget).
- **Auto-summarization** — long conversations are pruned/summarized to keep context tight.
- **Semantic search** — `/api/search?q=…` finds similar past chats (local embeddings).
- **Message integrity** — every saved message carries a SHA-256 hash; tampering is flagged.

All file/shell tools are confined to the **workspace folder** you grant access to.
Path traversal is blocked and archive extraction is checked for zip-slip escapes.

### Permissions (Claude-Code style)

Before any action that writes files or runs commands, Agent Studio can pause and ask
you to **Allow once**, **Allow all this run**, or **Deny**. Prefer unattended runs?
Switch to **Allow all** in Settings.

---

## Configuration (Settings)

- **API keys** — up to 3 NVIDIA NIM keys (the pool rotates across them).
- **Model** — `moonshotai/kimi-k2.6` (default) and other NIM presets, or a custom id.
- **Endpoint** — defaults to `https://integrate.api.nvidia.com/v1`. Extra regional
  endpoints can be added via the `KIMI_EXTRA_ENDPOINTS` env var (comma-separated).
- **Workspace path**, **temperature**, **max steps**, **tools on/off**,
  **permissions** (ask / allow-all), **swarm mode** (auto / off), and the **system prompt**.

---

## Architecture

```
START.command ─► backend (FastAPI, port 8000) ─► serves built frontend (React)
                      │
                      ├─ /api/chat            agent loop, streams NDJSON events
                      ├─ /api/settings        model + keys + workspace config
                      ├─ /api/conversations   history CRUD + integrity verify (SQLite)
                      ├─ /api/search          semantic search over past chats
                      ├─ /api/files           upload / download / list
                      └─ /api/permissions     approve / deny risky actions
```

- **Backend:** FastAPI · SQLAlchemy (SQLite) · OpenAI-compatible client → NVIDIA NIM
- **Frontend:** React 19 · Vite · Tailwind v4 · Zustand · Framer Motion

---

## Requirements

- macOS
- [Python 3.10+](https://www.python.org/downloads/macos/)
- Node.js 18+ *(only if you want to rebuild the UI from source)*

---

## Troubleshooting

- **Blank page / browser didn't open** — wait a few seconds and refresh
  <http://127.0.0.1:8000>; check the Terminal window for errors.
- **401 / invalid key** — re-paste your NVIDIA key in Settings.
- **Frontend build failed** — delete `frontend/node_modules` and run `START.command` again.
- **Port 8000 busy** — `START.command` frees it automatically.
