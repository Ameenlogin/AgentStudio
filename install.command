#!/bin/bash
# Agent Studio - first-time setup for macOS (optional; START.command does this too)
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
chmod +x "$DIR/START.command" "$DIR/run.command" 2>/dev/null || true

# ── Pretty, animated progress (spinner + bar; plain text when not a terminal) ─
C_ORANGE=$'\033[38;5;208m'; C_GREEN=$'\033[38;5;72m'; C_CYAN=$'\033[38;5;74m'
C_DIM=$'\033[2m'; C_RED=$'\033[31m'; C_BOLD=$'\033[1m'; C_RST=$'\033[0m'
SPIN=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
TOTAL_STEPS=4; CUR_STEP=0
anim() { [ -t 1 ] && [ "${TERM:-dumb}" != "dumb" ]; }
if ! anim; then C_ORANGE=; C_GREEN=; C_CYAN=; C_DIM=; C_RED=; C_BOLD=; C_RST=; fi
quit() { printf '\n  %s[ERROR]%s %s\n\n' "$C_RED" "$C_RST" "$*"; read -r -p "Press Return to close."; exit 1; }
bar() {
  local cur=$1 total=$2 width=28 i filled; [ "$total" -le 0 ] && total=1
  filled=$(( cur * width / total )); printf '  '
  for ((i=0; i<width; i++)); do
    if [ $i -lt $filled ]; then printf '%s█%s' "$C_ORANGE" "$C_RST"; else printf '%s░%s' "$C_DIM" "$C_RST"; fi
  done
  printf '  %s%d%%%s\n\n' "$C_BOLD" "$(( cur * 100 / total ))" "$C_RST"
}
step() {
  CUR_STEP=$((CUR_STEP+1)); local msg="$1"; shift
  local logf; logf="$(mktemp 2>/dev/null || echo "/tmp/as.$$.$CUR_STEP")"
  if anim; then
    "$@" >"$logf" 2>&1 & local pid=$! i=0 start=$SECONDS rc=0
    printf '\033[?25l'
    while kill -0 "$pid" 2>/dev/null; do
      printf '\r  %s%s%s  %s[%d/%d]%s %s %s(%ds)%s ' \
        "$C_ORANGE" "${SPIN[i++ % ${#SPIN[@]}]}" "$C_RST" "$C_DIM" "$CUR_STEP" "$TOTAL_STEPS" "$C_RST" \
        "$msg" "$C_DIM" "$((SECONDS-start))" "$C_RST"
      sleep 0.1
    done
    wait "$pid" || rc=$?; printf '\033[?25h'
    if [ "$rc" -eq 0 ]; then
      printf '\r  %s✓%s  %s[%d/%d]%s %s %s(%ds)%s\033[K\n' \
        "$C_GREEN" "$C_RST" "$C_DIM" "$CUR_STEP" "$TOTAL_STEPS" "$C_RST" "$msg" "$C_DIM" "$((SECONDS-start))" "$C_RST"
    else
      printf '\r  %s✗%s  %s[%d/%d]%s %s\033[K\n' "$C_RED" "$C_RST" "$C_DIM" "$CUR_STEP" "$TOTAL_STEPS" "$C_RST" "$msg"
      echo "  ----- details -----"; tail -25 "$logf" | sed 's/^/  /'; rm -f "$logf"; return "$rc"
    fi
  else
    printf '  [%d/%d] %s ... ' "$CUR_STEP" "$TOTAL_STEPS" "$msg"
    if "$@" >"$logf" 2>&1; then echo "done"; else echo "FAILED"; tail -25 "$logf"; rm -f "$logf"; return 1; fi
  fi
  rm -f "$logf"; bar "$CUR_STEP" "$TOTAL_STEPS"
}

printf '\n'
printf '  %s╔════════════════════════════════════════════════════════╗%s\n' "$C_ORANGE" "$C_RST"
printf '  %s║%s   %s✷ AGENT STUDIO%s  ·  First-Time Installation (macOS)     %s║%s\n' "$C_ORANGE" "$C_RST" "$C_BOLD" "$C_RST" "$C_ORANGE" "$C_RST"
printf '  %s╚════════════════════════════════════════════════════════╝%s\n\n' "$C_ORANGE" "$C_RST"

# Prerequisites (fast)
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; raise SystemExit(0 if sys.version_info[:2]>=(3,10) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
[ -n "$PY" ] || quit "Python 3.10+ not found.  brew install python  (or python.org)"
command -v node >/dev/null 2>&1 || quit "Node.js not found.  brew install node  (or https://nodejs.org)"
printf '  %s•%s Python %s   %s•%s Node %s\n\n' "$C_CYAN" "$C_RST" "$($PY --version 2>&1 | awk '{print $2}')" "$C_CYAN" "$C_RST" "$(node --version)"
VENV_PY="$DIR/backend/venv/bin/python"

do_venv()     { cd "$DIR/backend"; [ -x venv/bin/python ] || "$PY" -m venv venv; "$VENV_PY" -m pip install --upgrade pip -q --disable-pip-version-check; }
do_pip()      { cd "$DIR/backend"; "$VENV_PY" -m pip install -r requirements.txt -q --disable-pip-version-check; }
do_chromium() { cd "$DIR/backend"; "$VENV_PY" -m playwright install chromium >/dev/null 2>&1 || true; }
do_ui()       { cd "$DIR/frontend"; npm install --silent && npm run build; }

step "Creating the Python environment"        do_venv     || quit "Could not create the Python environment."
step "Installing backend packages"            do_pip      || quit "pip install failed (check internet)."
step "Installing the agent's Chrome browser"  do_chromium || true
step "Building the user interface"            do_ui       || quit "Frontend build failed (see details above)."

printf '  %s╔════════════════════════════════════════════════════════╗%s\n' "$C_GREEN" "$C_RST"
printf '  %s║%s   %s✓ Installation complete!%s  Double-click  run.command      %s║%s\n' "$C_GREEN" "$C_RST" "$C_BOLD" "$C_RST" "$C_GREEN" "$C_RST"
printf '  %s╚════════════════════════════════════════════════════════╝%s\n\n' "$C_GREEN" "$C_RST"
read -r -p "Press Return to close."
