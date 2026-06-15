# Agent Studio - one-command installer for Windows (PowerShell).
#
#   irm https://raw.githubusercontent.com/Ameenlogin/AgentStudio/main/install.ps1 | iex
#
# Clones (or updates) Agent Studio, sets everything up, and installs an
# `agent` command on your PATH. Afterwards open a NEW terminal and run:  agent run
$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/Ameenlogin/AgentStudio.git"
$Dest    = if ($env:AGENT_STUDIO_HOME) { $env:AGENT_STUDIO_HOME } else { Join-Path $HOME "AgentStudio" }
$BinDir  = Join-Path $env:LOCALAPPDATA "AgentStudio\bin"

Write-Host ""
Write-Host "  ==========================================================="
Write-Host "    AGENT STUDIO  -  installer (Windows)"
Write-Host "  ==========================================================="
Write-Host ""

# --- prerequisites ----------------------------------------------------------
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  throw "git is required. Install it from https://git-scm.com/download/win"
}

$PY = $null
foreach ($cand in @("py -3", "python")) {
  $exe, $pre = $cand.Split(" ", 2)
  if (Get-Command $exe -ErrorAction SilentlyContinue) {
    & cmd /c "$cand -c ""import sys; raise SystemExit(0 if sys.version_info[:2]>=(3,10) else 1)""" 2>$null
    if ($LASTEXITCODE -eq 0) { $PY = $cand; break }
  }
}
if (-not $PY) { throw "Python 3.10+ is required. Get it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH')." }
Write-Host "  Python: $PY  OK"

# --- clone or update --------------------------------------------------------
if (Test-Path (Join-Path $Dest ".git")) {
  Write-Host "  Updating existing install at $Dest ..."
  git -C $Dest pull --ff-only
} else {
  Write-Host "  Downloading Agent Studio to $Dest ..."
  git clone --depth 1 $RepoUrl $Dest
}

# --- backend (venv + packages) ----------------------------------------------
Write-Host "  Setting up the backend (Python venv + packages) ..."
Set-Location (Join-Path $Dest "backend")
$VenvPy = Join-Path $Dest "backend\venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) { & cmd /c "$PY -m venv venv" }
& $VenvPy -m pip install --upgrade pip -q --disable-pip-version-check
& $VenvPy -m pip install -r requirements.txt -q --disable-pip-version-check

# --- frontend (build if no prebuilt UI) -------------------------------------
Set-Location (Join-Path $Dest "frontend")
if (-not (Test-Path "dist\index.html")) {
  if (Get-Command node -ErrorAction SilentlyContinue) {
    Write-Host "  Building the user interface ..."
    if (-not (Test-Path "node_modules")) { npm install --silent }
    npm run build
  } else {
    Write-Host "  Note: Node.js not found and no prebuilt UI shipped."
    Write-Host "        Install Node.js (https://nodejs.org) and run 'agent install' to build it."
  }
}

# --- install the `agent` command --------------------------------------------
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
Copy-Item (Join-Path $Dest "bin\agent.cmd") (Join-Path $BinDir "agent.cmd") -Force

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$BinDir*") {
  [Environment]::SetEnvironmentVariable("Path", "$userPath;$BinDir", "User")
}

Write-Host ""
Write-Host "  ==========================================================="
Write-Host "    Installed!  Open a NEW terminal and run:"
Write-Host ""
Write-Host "        agent run"
Write-Host ""
Write-Host "  ==========================================================="
Write-Host ""
