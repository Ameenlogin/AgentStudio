#!/usr/bin/env bash
# Agent Studio — one-command installer for macOS & Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/Ameenlogin/AgentStudio/main/install.sh | bash
#
# Clones (or updates) Agent Studio, sets everything up, and installs an
# `agent` command on your PATH. Afterwards just run:  agent run
set -euo pipefail

REPO_URL="https://github.com/Ameenlogin/AgentStudio.git"
DEST="${AGENT_STUDIO_HOME:-$HOME/AgentStudio}"
BIN_DIR="$HOME/.local/bin"

say()  { printf '  %s\n' "$*"; }
die()  { printf '\n  [ERROR] %s\n\n' "$*" >&2; exit 1; }

printf '\n  ===========================================================\n'
printf '    AGENT STUDIO  -  installer (macOS / Linux)\n'
printf '  ===========================================================\n\n'

# --- prerequisites ----------------------------------------------------------
command -v git >/dev/null 2>&1 || die "git is required. Install Xcode CLT (xcode-select --install) or git-scm.com."

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; raise SystemExit(0 if sys.version_info[:2]>=(3,10) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || die "Python 3.10+ is required. Get it from https://www.python.org/downloads/ (or: brew install python)."
say "Python: $($PY --version 2>&1)"

# --- clone or update --------------------------------------------------------
if [ -d "$DEST/.git" ]; then
  say "Updating existing install at $DEST ..."
  git -C "$DEST" pull --ff-only || say "(could not fast-forward; keeping current version)"
else
  say "Downloading Agent Studio to $DEST ..."
  git clone --depth 1 "$REPO_URL" "$DEST"
fi

# --- backend (venv + packages) ----------------------------------------------
say "Setting up the backend (Python venv + packages) ..."
cd "$DEST/backend"
[ -x venv/bin/python ] || "$PY" -m venv venv
venv/bin/python -m pip install --upgrade pip -q --disable-pip-version-check
venv/bin/python -m pip install -r requirements.txt -q --disable-pip-version-check

# --- frontend (build if no prebuilt UI) -------------------------------------
cd "$DEST/frontend"
if [ ! -f dist/index.html ]; then
  if command -v node >/dev/null 2>&1; then
    say "Building the user interface ..."
    [ -d node_modules ] || npm install --silent
    npm run build
  else
    say "Note: Node.js not found and no prebuilt UI shipped."
    say "      Install Node.js (https://nodejs.org) and run 'agent install' to build it."
  fi
fi

# --- install the `agentstudio` command --------------------------------------
mkdir -p "$BIN_DIR"
cp "$DEST/bin/agentstudio" "$BIN_DIR/agentstudio"
chmod +x "$BIN_DIR/agentstudio"

# Remove a stale `agent` shim from an older Agent Studio install (only if ours).
if [ -f "$BIN_DIR/agent" ] && grep -q "AGENT_STUDIO_HOME" "$BIN_DIR/agent" 2>/dev/null; then
  rm -f "$BIN_DIR/agent"
fi
# Also offer the short `agent` name — but ONLY if no other tool already uses it.
ALIAS_NOTE=""
if ! command -v agent >/dev/null 2>&1; then
  cp "$DEST/bin/agentstudio" "$BIN_DIR/agent"
  chmod +x "$BIN_DIR/agent"
  ALIAS_NOTE='  (short alias also works: agent run)'
fi

# Ensure ~/.local/bin is on PATH for future shells.
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

printf '\n  ===========================================================\n'
printf '    Installed!  Start Agent Studio with:\n\n'
printf '        agentstudio run\n'
[ -n "$ALIAS_NOTE" ] && printf '      %s\n' "$ALIAS_NOTE"
printf '\n'
if [ "$NEEDS_NEW_SHELL" = "1" ]; then
  printf '    First time: open a NEW terminal (or run:  source ~/.zshrc )\n'
  printf '    so the command is found — or run it right now with:\n\n'
  printf '        %s/agentstudio run\n' "$BIN_DIR"
fi
printf '  ===========================================================\n\n'
