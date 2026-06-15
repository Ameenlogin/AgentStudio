#!/bin/bash
# Agent Studio - one-click launcher for macOS
# Double-click in Finder. First run sets up anything missing, then starts the
# app and opens it in your browser. Python-only when the UI is prebuilt.

set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Make the sibling launchers executable too (zip/download can drop the bit)
chmod +x "$DIR/run.command" "$DIR/install.command" 2>/dev/null || true

printf '\n'
printf '  ============================================================\n'
printf '     AGENT STUDIO   |   macOS Launcher\n'
printf '  ============================================================\n\n'

# --- pick a Python 3 ---------------------------------------------------------
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then
    if "$c" -c 'import sys; raise SystemExit(0 if sys.version_info[:2]>=(3,10) else 1)' 2>/dev/null; then
      PY="$c"; break
    fi
  fi
done
if [ -z "$PY" ]; then
  printf '  [ERROR] Python 3.10+ not found.\n'
  printf '  Install it with Homebrew:  brew install python\n'
  printf '  or download from:          https://www.python.org/downloads/macos/\n\n'
  read -r -p "Press Return to close."
  exit 1
fi
printf '  [1/4] Python: %s  OK\n' "$($PY --version 2>&1)"

# --- backend venv + packages -------------------------------------------------
printf '  [2/4] Preparing backend...\n'
cd "$DIR/backend"
if [ ! -x "venv/bin/python" ]; then
  printf '        Creating virtual environment...\n'
  "$PY" -m venv venv || { printf '  [ERROR] Could not create venv.\n'; read -r -p "Press Return."; exit 1; }
fi
VENV_PY="$DIR/backend/venv/bin/python"
if ! "$VENV_PY" -c 'import uvicorn, fastapi, openai, sqlalchemy, pypdf, fpdf, lxml, bs4, requests' >/dev/null 2>&1; then
  printf '        Installing backend packages (first run, ~30s)...\n'
  "$VENV_PY" -m pip install --upgrade pip -q --disable-pip-version-check
  "$VENV_PY" -m pip install -r requirements.txt --disable-pip-version-check \
    || { printf '  [ERROR] pip install failed (check internet).\n'; read -r -p "Press Return."; exit 1; }
else
  printf '        Backend packages already installed.\n'
fi
printf '        OK\n'

# --- user interface ----------------------------------------------------------
printf '  [3/4] Preparing user interface...\n'
cd "$DIR/frontend"
if [ -f "dist/index.html" ]; then
  printf '        Prebuilt UI found - skipping Node setup.\n'
else
  printf '        No prebuilt UI - building from source (needs Node.js)...\n'
  if ! command -v node >/dev/null 2>&1; then
    printf '  [ERROR] Node.js not found and no prebuilt UI.\n'
    printf '  Install it:  brew install node   (or https://nodejs.org)\n\n'
    read -r -p "Press Return."; exit 1
  fi
  [ -d node_modules ] || { printf '        npm install (~60s)...\n'; npm install || { read -r -p "npm install failed. Press Return."; exit 1; }; }
  printf '        Building (~30s)...\n'
  npm run build || { printf '  [ERROR] Build failed (see above).\n'; read -r -p "Press Return."; exit 1; }
fi
printf '        OK\n'

# --- free port 8000 ----------------------------------------------------------
PIDS="$(lsof -ti tcp:8000 2>/dev/null || true)"
if [ -n "$PIDS" ]; then
  printf '  [4/4] Stopping old process on port 8000...\n'
  echo "$PIDS" | xargs kill -9 2>/dev/null || true
  sleep 1
else
  printf '  [4/4] Starting server...\n'
fi

# Open the browser as soon as the server answers, in the background.
(
  for _ in $(seq 1 40); do
    sleep 1
    if curl -s -o /dev/null "http://127.0.0.1:8000/api/health" 2>/dev/null; then
      open "http://127.0.0.1:8000"
      exit 0
    fi
  done
) &

printf '\n'
printf '  ============================================================\n'
printf '     AGENT STUDIO is starting at http://127.0.0.1:8000\n'
printf '     Your browser opens automatically when ready.\n'
printf '     To STOP: press Ctrl+C here, or close this window.\n'
printf '  ============================================================\n\n'

# Run the server in the FOREGROUND so logs are visible and Ctrl+C stops it.
cd "$DIR/backend"
exec "$VENV_PY" -m uvicorn main:app --host 127.0.0.1 --port 8000
