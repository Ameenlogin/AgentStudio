#!/usr/bin/env bash
# Agent Studio — one-command installer for macOS & Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/Ameenlogin/AgentStudio/main/install.sh | bash
#
# Clones (or updates) Agent Studio, sets everything up, and installs an
# `agentstudio` command on your PATH. Afterwards just run:  agentstudio run
set -euo pipefail

REPO_URL="https://github.com/Ameenlogin/AgentStudio.git"
DEST="${AGENT_STUDIO_HOME:-$HOME/AgentStudio}"
BIN_DIR="$HOME/.local/bin"

# ── Pretty, animated progress ────────────────────────────────────────────────
# Long installs feel less boring (and people don't quit) when each step shows a
# live spinner + elapsed time and an overall progress bar. Falls back to plain
# text when output isn't a terminal (e.g. piped into a log).
C_ORANGE=$'\033[38;5;208m'; C_GREEN=$'\033[38;5;72m'; C_CYAN=$'\033[38;5;74m'
C_DIM=$'\033[2m'; C_RED=$'\033[31m'; C_BOLD=$'\033[1m'; C_RST=$'\033[0m'
SPIN=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
TOTAL_STEPS=0; CUR_STEP=0
anim() { [ -t 1 ] && [ "${TERM:-dumb}" != "dumb" ]; }
if ! anim; then C_ORANGE=; C_GREEN=; C_CYAN=; C_DIM=; C_RED=; C_BOLD=; C_RST=; fi

say()  { printf '  %s\n' "$*"; }
die()  { printf '\n  %s[ERROR]%s %s\n\n' "$C_RED" "$C_RST" "$*" >&2; exit 1; }

bar() { # bar <cur> <total>
  local cur=$1 total=$2 width=28 i filled; [ "$total" -le 0 ] && total=1
  filled=$(( cur * width / total )); printf '  '
  for ((i=0; i<width; i++)); do
    if [ $i -lt $filled ]; then printf '%s█%s' "$C_ORANGE" "$C_RST"; else printf '%s░%s' "$C_DIM" "$C_RST"; fi
  done
  printf '  %s%d%%%s\n\n' "$C_BOLD" "$(( cur * 100 / total ))" "$C_RST"
}

step() { # step "Message" command [args...]
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
printf '  %s║%s   %s✷ AGENT STUDIO%s  ·  your private NVIDIA-powered agent   %s║%s\n' "$C_ORANGE" "$C_RST" "$C_BOLD" "$C_RST" "$C_ORANGE" "$C_RST"
printf '  %s╚════════════════════════════════════════════════════════╝%s\n\n' "$C_ORANGE" "$C_RST"
printf '  %sSetting things up — keep this window open, it only takes a minute.%s\n\n' "$C_DIM" "$C_RST"

# ── Prerequisites (fast, no animation) ───────────────────────────────────────
command -v git >/dev/null 2>&1 || die "git is required. Install Xcode CLT (xcode-select --install) or git-scm.com."
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; raise SystemExit(0 if sys.version_info[:2]>=(3,10) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || die "Python 3.10+ is required. Get it from https://www.python.org/downloads/ (or: brew install python)."
say "${C_CYAN}•${C_RST} Python $("$PY" --version 2>&1 | awk '{print $2}')   ${C_CYAN}•${C_RST} git $(git --version 2>&1 | awk '{print $3}')"
HAS_NODE=0; command -v node >/dev/null 2>&1 && HAS_NODE=1
printf '\n'

# ── Step functions (each runs inside step's spinner) ─────────────────────────
do_fetch() {
  if [ -d "$DEST/.git" ]; then git -C "$DEST" pull --ff-only || true; else git clone --depth 1 "$REPO_URL" "$DEST"; fi
}
do_venv() {
  cd "$DEST/backend"; [ -x venv/bin/python ] || "$PY" -m venv venv
  venv/bin/python -m pip install --upgrade pip -q --disable-pip-version-check
}
do_pip() { cd "$DEST/backend"; venv/bin/python -m pip install -r requirements.txt -q --disable-pip-version-check; }
# Best-effort: a failed Chromium download must NOT abort the install (the agent's
# browser tools prompt to retry at first use), so this always returns success.
do_chromium() { cd "$DEST/backend"; venv/bin/python -m playwright install chromium >/dev/null 2>&1 || true; }
do_ui() { cd "$DEST/frontend"; npm install --silent && npm run build; }
do_command() {
  mkdir -p "$BIN_DIR"
  cp "$DEST/bin/agentstudio" "$BIN_DIR/agentstudio"; chmod +x "$BIN_DIR/agentstudio"
  if [ -f "$BIN_DIR/agent" ] && grep -q "AGENT_STUDIO_HOME" "$BIN_DIR/agent" 2>/dev/null; then rm -f "$BIN_DIR/agent"; fi
  if ! command -v agent >/dev/null 2>&1; then cp "$DEST/bin/agentstudio" "$BIN_DIR/agent"; chmod +x "$BIN_DIR/agent"; fi
}

# Count the steps that will actually run (so the bar reaches 100%).
TOTAL_STEPS=5; [ "$HAS_NODE" -eq 1 ] && TOTAL_STEPS=6

step "Downloading Agent Studio"                      do_fetch     || die "Could not download Agent Studio (check your connection)."
step "Creating the Python environment"               do_venv      || die "Could not create the Python environment."
step "Installing backend packages"                   do_pip       || die "pip install failed (check your connection)."
step "Installing the agent's Chrome browser"         do_chromium  || true
if [ "$HAS_NODE" -eq 1 ]; then
  step "Building the user interface"                 do_ui        || die "Frontend build failed (see details above)."
else
  say "${C_DIM}Note: Node.js not found — using the prebuilt UI if present. Install Node.js + run 'agentstudio update' to rebuild.${C_RST}"
fi
step "Installing the 'agentstudio' command"          do_command   || die "Could not install the command."

# ── PATH wiring (fast) ───────────────────────────────────────────────────────
ALIAS_NOTE=""
command -v agent >/dev/null 2>&1 && [ -f "$BIN_DIR/agent" ] && ALIAS_NOTE='  (short alias also works: agent run)'
NEEDS_NEW_SHELL=0
case ":${PATH}:" in
  *":$BIN_DIR:"*) : ;;
  *)
    NEEDS_NEW_SHELL=1
    for rc in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.profile"; do
      [ -e "$rc" ] || continue
      grep -q 'AgentStudio: PATH' "$rc" 2>/dev/null && continue
      printf '\n# AgentStudio: PATH\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$rc"
    done
    ;;
esac

printf '  %s╔════════════════════════════════════════════════════════╗%s\n' "$C_GREEN" "$C_RST"
printf '  %s║%s   %s✓ All set!%s  Start Agent Studio with:                     %s║%s\n' "$C_GREEN" "$C_RST" "$C_BOLD" "$C_RST" "$C_GREEN" "$C_RST"
printf '  %s║%s                                                          %s║%s\n' "$C_GREEN" "$C_RST" "$C_GREEN" "$C_RST"
printf '  %s║%s        %sagentstudio run%s                                   %s║%s\n' "$C_GREEN" "$C_RST" "$C_BOLD$C_ORANGE" "$C_RST" "$C_GREEN" "$C_RST"
printf '  %s╚════════════════════════════════════════════════════════╝%s\n' "$C_GREEN" "$C_RST"
[ -n "$ALIAS_NOTE" ] && printf '  %s%s%s\n' "$C_DIM" "$ALIAS_NOTE" "$C_RST"
printf '\n'
if [ "$NEEDS_NEW_SHELL" = "1" ]; then
  printf '  First time: open a NEW terminal (or run:  source ~/.zshrc )\n'
  printf '  so the command is found — or run it right now with:\n\n'
  printf '        %s/agentstudio run\n\n' "$BIN_DIR"
fi
