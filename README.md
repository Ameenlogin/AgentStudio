<div align="center">

# ✳️ Agent Studio

### The best local app for your **NVIDIA NIM API key** — a free, private, Claude Code-style AI coding agent for **macOS & Windows**.

Turn a free [NVIDIA NIM](https://build.nvidia.com) key into a full autonomous engineering agent that **plans, writes code, runs tools, and ships** — running 100% on your own machine, powered by **Moonshot Kimi K2** and other NIM models.

![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-black)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![price](https://img.shields.io/badge/price-free-brightgreen)
![runs](https://img.shields.io/badge/runs-100%25%20local-orange)

</div>

---

## Why Agent Studio?

If you have a **free NVIDIA NIM API key**, this is the easiest and most powerful way to use it. Agent Studio is a **local, open AI coding agent** — a free alternative to cloud coding assistants — with a live "thinking + tool execution" timeline. Your key, your machine, your files: nothing is sent to a third-party server.

- 🔑 **Built for NVIDIA NIM** — paste your key once in the app and go. No `.env` editing, no cloud account.
- 🖥️ **macOS *and* Windows** — one-click launchers for both. Anyone can clone and run it.
- 🧠 **Truly agentic** — it doesn't just chat; it reads/writes files, runs shell & Python, searches the web, edits archives, and verifies its own work.
- 🆓 **Free & private** — runs entirely on `localhost`. Uses *your* NIM key (free tier available from NVIDIA).
- ⚡ **Fast** — a two-speed router answers simple questions instantly and only spins up the full tool loop when a task needs it.

---

## 🚀 Quick start

You need **Python 3.10+** (and **Node.js 18+** only if the prebuilt UI isn't included). Then two steps:

### macOS

| Step | Do this |
|------|---------|
| **1. Install (first time)** | Double-click **`install.command`** |
| **2. Run (every time)** | Double-click **`run.command`** |

> Prefer one file? **`START.command`** sets up *and* runs in a single double-click.
> If macOS blocks it, run once in Terminal: `chmod +x *.command && xattr -dr com.apple.quarantine .`

### Windows

| Step | Do this |
|------|---------|
| **1. Install (first time)** | Double-click **`install.bat`** |
| **2. Run (every time)** | Double-click **`run.bat`** |

> Prefer one file? **`START.bat`** sets up *and* runs in a single double-click.

Either way, your browser **opens automatically** at **<http://127.0.0.1:8000>** when the app is ready. To stop it, press `Ctrl+C` in the window or close it.

### Add your API key (first run)

1. Get a **free** key at **[build.nvidia.com](https://build.nvidia.com)** (sign in → any model → *Get API Key*).
2. Agent Studio opens with a prompt to add it — paste it into **Settings → API key** and save.
3. Start chatting. That's it.

---

## ✨ What it can do

Give it a task and it plans, calls real tools on your machine, observes the results, and keeps going until the job is done — streamed live so you can watch it think and act.

| Group | Capabilities |
|-------|--------------|
| **Files** | read (with **large-file paging**), write, append, edit, move, copy, delete · **batch** read & write · recursive tree · **regex grep** & glob · **bulk find-and-replace** across files · precise unified-diff **`apply_patch`** |
| **Archives** | create / extract / list zips **and edit files in place inside a zip** without unpacking |
| **PDFs** | extract text, inspect, and **create PDFs** from text/Markdown |
| **Code** | run shell commands & Python with **live streamed output** · `pip install` missing libraries · full `git` |
| **Web** | search, fetch readable text, scrape by CSS selector, extract links, raw HTTP, downloads |
| **Skills** | install reusable expertise packs from any public GitHub repo |

It can build complete **websites & web apps**, **WordPress themes/plugins (PHP)**, CLIs, scripts, data pipelines, design assets, documents and PDFs — then package the result into a downloadable zip.

---

## 🛠️ Under the hood

- **Two-speed router** — trivial/conversational messages get one fast streamed reply; real tasks run the full plan→act→observe loop.
- **Knows when to stop** — a no-progress guard detects an agent repeating itself (same tool call or re-emitting the same answer) and finishes cleanly instead of looping. No more "report regenerated forever."
- **Large-file & large-codebase handling** — `read_file` pages through huge files by line range, and `grep`/`glob`/`tree` jump straight to what matters.
- **Bulk / parallel actions** — independent read-only tool calls in a turn run concurrently; batch read/write and `apply_patch` change many files at once.
- **Multi-agent swarm** *(auto, for complex tasks)* — `Planner → parallel research workers → Builder → Synthesizer`.
- **Live tool streaming** — shell/Python output streams to the UI line-by-line.
- **Rate-aware key pool** — requests are spread under NVIDIA's RPM limit with automatic back-off, so you never trip a 429.
- **Semantic cache + search** — near-identical questions answer instantly from a local embedding cache (zero extra API calls); past chats are searchable.
- **Persistent, separate sessions** — every conversation is saved independently in local SQLite, each message carrying a SHA-256 integrity hash.

All file/shell tools are confined to the **workspace folder** you grant access to; path traversal and zip-slip are blocked. Before any write or command, Agent Studio can **Allow once / Allow all / Deny** — or run unattended in *Allow all* mode.

---

## 🧩 Architecture

```
START / install / run  ─►  backend (FastAPI, :8000)  ─►  serves built React UI
                                  │
                                  ├─ /api/chat            streaming agent loop (NDJSON)
                                  ├─ /api/settings        model · API key · workspace
                                  ├─ /api/conversations   history + integrity (SQLite)
                                  ├─ /api/search          semantic search over chats
                                  ├─ /api/files           upload / download / list
                                  └─ /api/permissions     approve / deny risky actions
```

- **Backend:** FastAPI · SQLAlchemy (SQLite) · OpenAI-compatible client → NVIDIA NIM
- **Frontend:** React 19 · Vite · Tailwind v4 · Zustand · Framer Motion
- **Models:** `moonshotai/kimi-k2.6` (default), GPT-OSS 120B/20B, Llama 3.3 70B, Nemotron 49B, Qwen3-Next 80B — all on NVIDIA NIM.

---

## ✅ Requirements

- **macOS** or **Windows 10/11**
- [Python 3.10+](https://www.python.org/downloads/) (on Windows, tick *"Add python.exe to PATH"*)
- [Node.js 18+](https://nodejs.org) *(only needed to build the UI from source)*
- A free **NVIDIA NIM API key** — [build.nvidia.com](https://build.nvidia.com)

---

## 🩹 Troubleshooting

- **Browser didn't open** — wait a moment and visit <http://127.0.0.1:8000>; check the launcher window for errors.
- **"API key not configured"** — add your NVIDIA NIM key in **Settings**.
- **401 / invalid key** — re-paste the key in Settings.
- **Port 8000 busy** — the launchers free it automatically.
- **Build failed** — delete `frontend/node_modules` and run the installer again.

---

<div align="center">
<sub>

**Keywords:** NVIDIA NIM API key · local AI coding agent · free Claude Code alternative · Kimi K2 · Moonshot AI · autonomous coding agent · self-hosted AI assistant · NVIDIA build.nvidia.com · macOS & Windows AI agent · open source coding agent

</sub>
</div>
