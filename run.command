#!/bin/bash
# Agent Studio - start the app on macOS (assumes setup is done; else use START.command)
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
chmod +x "$DIR/START.command" "$DIR/install.command" 2>/dev/null || true

VENV_PY="$DIR/backend/venv/bin/python"
if [ ! -x "$VENV_PY" ] || [ ! -f "$DIR/frontend/dist/index.html" ]; then
  printf '\n  [ERROR] Setup not complete.\n'
  printf '  Double-click  START.command  instead - it sets up everything.\n\n'
  read -r -p "Press Return to close."; exit 1
fi

# Free port 8000
PIDS="$(lsof -ti tcp:8000 2>/dev/null || true)"
if [ -n "$PIDS" ]; then
  printf '  Stopping old process on port 8000...\n'
  echo "$PIDS" | xargs kill -9 2>/dev/null || true
  sleep 1
fi

(
  for _ in $(seq 1 30); do
    sleep 1
    if curl -s -o /dev/null "http://127.0.0.1:8000/api/health" 2>/dev/null; then
      open "http://127.0.0.1:8000"; exit 0
    fi
  done
) &

printf '\n  ==========================================================\n'
printf '    Agent Studio is starting at http://127.0.0.1:8000\n'
printf '    Browser opens automatically. Ctrl+C or close to stop.\n'
printf '  ==========================================================\n\n'

cd "$DIR/backend"
exec "$VENV_PY" -m uvicorn main:app --host 127.0.0.1 --port 8000
