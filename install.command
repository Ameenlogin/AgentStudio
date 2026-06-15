#!/bin/bash
# Agent Studio - first-time setup for macOS (optional; START.command does this too)
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
chmod +x "$DIR/START.command" "$DIR/run.command" 2>/dev/null || true

printf '\n  ==========================================================\n'
printf '    AGENT STUDIO  |  First-Time Installation (macOS)\n'
printf '  ==========================================================\n\n'

# 1) Python
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; raise SystemExit(0 if sys.version_info[:2]>=(3,10) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  printf '  [ERROR] Python 3.10+ not found.  brew install python  (or python.org)\n\n'
  read -r -p "Press Return to close."; exit 1
fi
printf '  [1/5] Python: %s  OK\n' "$($PY --version 2>&1)"

# 2) Node
printf '  [2/5] Checking Node.js...\n'
if ! command -v node >/dev/null 2>&1; then
  printf '  [ERROR] Node.js not found.  brew install node  (or https://nodejs.org)\n\n'
  read -r -p "Press Return to close."; exit 1
fi
printf '        %s  OK\n' "$(node --version)"

# 3) venv
printf '  [3/5] Creating Python virtual environment...\n'
cd "$DIR/backend"
if [ -x "venv/bin/python" ]; then
  printf '        Already exists, skipping.\n'
else
  "$PY" -m venv venv || { printf '  [ERROR] venv creation failed.\n'; read -r -p "Press Return."; exit 1; }
  printf '        Created.\n'
fi
VENV_PY="$DIR/backend/venv/bin/python"

# 4) backend packages
printf '  [4/5] Installing backend packages (~30s)...\n'
"$VENV_PY" -m pip install --upgrade pip -q --disable-pip-version-check
"$VENV_PY" -m pip install -r requirements.txt --disable-pip-version-check \
  || { printf '  [ERROR] pip install failed (check internet).\n'; read -r -p "Press Return."; exit 1; }
printf '        Backend packages installed.\n'

# 5) frontend
printf '  [5/5] Installing and building frontend (~60s)...\n'
cd "$DIR/frontend"
npm install || { printf '  [ERROR] npm install failed.\n'; read -r -p "Press Return."; exit 1; }
npm run build || { printf '  [ERROR] Frontend build failed (see above).\n'; read -r -p "Press Return."; exit 1; }
printf '        Frontend built.\n'

printf '\n  ==========================================================\n'
printf '    Installation COMPLETE!  Now double-click  run.command\n'
printf '  ==========================================================\n\n'
read -r -p "Press Return to close."
