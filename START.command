#!/bin/bash
# Agent Studio - one-click launcher for macOS
# Double-click in Finder. First run sets up anything missing, then starts the
# app and opens it in your browser. Python-only when the UI is prebuilt.

set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Make the sibling launchers executable too (zip/download can drop the bit)
chmod +x "$DIR/run.command" "$DIR/install.command" 2>/dev/null || true

# ── Pretty spinner (live elapsed; plain text when not a terminal) ─────────────
C_ORANGE=$'\033[38;5;208m'; C_GREEN=$'\033[38;5;72m'; C_CYAN=$'\033[38;5;74m'
C_DIM=$'\033[2m'; C_RED=$'\033[31m'; C_BOLD=$'\033[1m'; C_RST=$'\033[0m'
SPIN=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
anim() { [ -t 1 ] && [ "${TERM:-dumb}" != "dumb" ]; }
if ! anim; then C_ORANGE=; C_GREEN=; C_CYAN=; C_DIM=; C_RED=; C_BOLD=; C_RST=; fi
quit() { printf '\n  %s[ERROR]%s %s\n\n' "$C_RED" "$C_RST" "$*"; read -r -p "Press Return to close."; exit 1; }
ok()   { printf '  %s✓%s %s\n' "$C_GREEN" "$C_RST" "$*"; }
spin() { # spin "Message" command [args...]
  local msg="$1"; shift
  local logf; logf="$(mktemp 2>/dev/null || echo "/tmp/as.$$")"
  if anim; then
    "$@" >"$logf" 2>&1 & local pid=$! i=0 start=$SECONDS rc=0
    printf '\033[?25l'
    while kill -0 "$pid" 2>/dev/null; do
      printf '\r  %s%s%s %s %s(%ds)%s ' "$C_ORANGE" "${SPIN[i++ % ${#SPIN[@]}]}" "$C_RST" "$msg" "$C_DIM" "$((SECONDS-start))" "$C_RST"
      sleep 0.1
    done
    wait "$pid" || rc=$?; printf '\033[?25h'
    if [ "$rc" -eq 0 ]; then printf '\r  %s✓%s %s %s(%ds)%s\033[K\n' "$C_GREEN" "$C_RST" "$msg" "$C_DIM" "$((SECONDS-start))" "$C_RST"
    else printf '\r  %s✗%s %s\033[K\n' "$C_RED" "$C_RST" "$msg"; echo "  ----- details -----"; tail -25 "$logf" | sed 's/^/  /'; rm -f "$logf"; return "$rc"; fi
  else
    printf '  %s ... ' "$msg"
    if "$@" >"$logf" 2>&1; then echo "done"; else echo "FAILED"; tail -25 "$logf"; rm -f "$logf"; return 1; fi
  fi
  rm -f "$logf"
}

printf '\n'
printf '  %s╔════════════════════════════════════════════════════════╗%s\n' "$C_ORANGE" "$C_RST"
printf '  %s║%s   %s✷ AGENT STUDIO%s  ·  macOS Launcher                      %s║%s\n' "$C_ORANGE" "$C_RST" "$C_BOLD" "$C_RST" "$C_ORANGE" "$C_RST"
printf '  %s╚════════════════════════════════════════════════════════╝%s\n\n' "$C_ORANGE" "$C_RST"

# --- pick a Python 3 ---------------------------------------------------------
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then
    if "$c" -c 'import sys; raise SystemExit(0 if sys.version_info[:2]>=(3,10) else 1)' 2>/dev/null; then PY="$c"; break; fi
  fi
done
[ -n "$PY" ] || quit "Python 3.10+ not found. Install:  brew install python  (or https://www.python.org/downloads/macos/)"
ok "Python $($PY --version 2>&1 | awk '{print $2}')"

# --- backend venv + packages -------------------------------------------------
cd "$DIR/backend"
[ -x "venv/bin/python" ] || spin "Creating the Python environment" "$PY" -m venv venv || quit "Could not create venv."
VENV_PY="$DIR/backend/venv/bin/python"
do_pip() { "$VENV_PY" -m pip install --upgrade pip -q --disable-pip-version-check && "$VENV_PY" -m pip install -r requirements.txt -q --disable-pip-version-check; }
do_chromium() { "$VENV_PY" -m playwright install chromium >/dev/null 2>&1 || true; }
if "$VENV_PY" -c 'import uvicorn, fastapi, openai, sqlalchemy, pypdf, fpdf, lxml, bs4, requests, playwright' >/dev/null 2>&1; then
  ok "Backend packages ready"
else
  spin "Installing backend packages (first run)" do_pip || quit "pip install failed (check internet)."
fi
spin "Preparing the agent's Chrome browser" do_chromium || true

# --- user interface ----------------------------------------------------------
cd "$DIR/frontend"
if [ -f "dist/index.html" ]; then
  ok "User interface ready (prebuilt)"
else
  command -v node >/dev/null 2>&1 || quit "Node.js not found and no prebuilt UI. Install:  brew install node  (or https://nodejs.org)"
  do_ui() { npm install --silent && npm run build; }
  spin "Building the user interface" do_ui || quit "Build failed (see details above)."
fi

# --- free port 8000 ----------------------------------------------------------
PIDS="$(lsof -ti tcp:8000 2>/dev/null || true)"
[ -n "$PIDS" ] && { echo "$PIDS" | xargs kill -9 2>/dev/null || true; sleep 1; }

# Open the browser as soon as the server answers, in the background.
(
  for _ in $(seq 1 40); do
    sleep 1
    if curl -s -o /dev/null "http://127.0.0.1:8000/api/health" 2>/dev/null; then open "http://127.0.0.1:8000"; exit 0; fi
  done
) &

printf '\n'
printf '  %s╔════════════════════════════════════════════════════════╗%s\n' "$C_GREEN" "$C_RST"
printf '  %s║%s   %s✓ Starting%s at  %shttp://127.0.0.1:8000%s                  %s║%s\n' "$C_GREEN" "$C_RST" "$C_BOLD" "$C_RST" "$C_BOLD$C_ORANGE" "$C_RST" "$C_GREEN" "$C_RST"
printf '  %s║%s   Your browser opens automatically when ready.           %s║%s\n' "$C_GREEN" "$C_RST" "$C_GREEN" "$C_RST"
printf '  %s║%s   To STOP: press Ctrl+C here, or close this window.      %s║%s\n' "$C_GREEN" "$C_RST" "$C_GREEN" "$C_RST"
printf '  %s╚════════════════════════════════════════════════════════╝%s\n\n' "$C_GREEN" "$C_RST"

# Run the server in the FOREGROUND so logs are visible and Ctrl+C stops it.
cd "$DIR/backend"
exec "$VENV_PY" -m uvicorn main:app --host 127.0.0.1 --port 8000
