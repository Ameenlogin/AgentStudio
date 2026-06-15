# Agent Studio - one-command installer for Windows (PowerShell).
#
#   irm https://raw.githubusercontent.com/Ameenlogin/AgentStudio/main/install.ps1 | iex
#
# Clones (or updates) Agent Studio, sets everything up, and installs an
# `agentstudio` command on your PATH. Afterwards open a NEW terminal: agentstudio run
$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/Ameenlogin/AgentStudio.git"
$Dest    = if ($env:AGENT_STUDIO_HOME) { $env:AGENT_STUDIO_HOME } else { Join-Path $HOME "AgentStudio" }
$BinDir  = Join-Path $env:LOCALAPPDATA "AgentStudio\bin"

# ── Progress (native Write-Progress bar + colored, timed step lines) ─────────
# A long, silent install makes people quit. We keep the exact, proven install
# commands and wrap them with a real progress bar plus a green "done (Xs)" line
# per step — transparent and reassuring, with zero risk of mangling commands.
$script:Total = 6; $script:Cur = 0
function Start-Step([string]$Msg) {
  $script:Cur++
  $pct = [int](($script:Cur - 1) * 100 / $script:Total)
  Write-Progress -Activity "Installing Agent Studio" -Status "[$($script:Cur)/$($script:Total)] $Msg" -PercentComplete $pct
  Write-Host ("  -> [{0}/{1}] {2} ..." -f $script:Cur, $script:Total, $Msg) -ForegroundColor Cyan -NoNewline
  return [Diagnostics.Stopwatch]::StartNew()
}
function Stop-Step($sw) {
  Write-Progress -Activity "Installing Agent Studio" -Status "Done" -PercentComplete ([int]($script:Cur * 100 / $script:Total))
  Write-Host ("  done ({0}s)" -f [int]$sw.Elapsed.TotalSeconds) -ForegroundColor Green
}

Write-Host ""
Write-Host "  +========================================================+" -ForegroundColor DarkYellow
Write-Host "  |   * AGENT STUDIO  -  your private NVIDIA-powered agent  |" -ForegroundColor Yellow
Write-Host "  +========================================================+" -ForegroundColor DarkYellow
Write-Host "  Setting things up - keep this window open, it only takes a minute." -ForegroundColor DarkGray
Write-Host ""

# --- prerequisites (fast) ----------------------------------------------------
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
$HasNode = [bool](Get-Command node -ErrorAction SilentlyContinue)
if (-not $HasNode) { $script:Total = 5 }
Write-Host "  * Python ($PY)$(if($HasNode){'   * Node ' + (node --version)})" -ForegroundColor Cyan
Write-Host ""

# --- clone or update ---------------------------------------------------------
$fetchMsg = if (Test-Path (Join-Path $Dest ".git")) { "Updating Agent Studio" } else { "Downloading Agent Studio" }
$sw = Start-Step $fetchMsg
if (Test-Path (Join-Path $Dest ".git")) { git -C $Dest pull --ff-only } else { git clone --depth 1 $RepoUrl $Dest }
Stop-Step $sw

# --- backend (venv + packages) ----------------------------------------------
Set-Location (Join-Path $Dest "backend")
$VenvPy = Join-Path $Dest "backend\venv\Scripts\python.exe"
$sw = Start-Step "Creating the Python environment"
if (-not (Test-Path $VenvPy)) { & cmd /c "$PY -m venv venv" }
& $VenvPy -m pip install --upgrade pip -q --disable-pip-version-check
Stop-Step $sw

$sw = Start-Step "Installing backend packages"
& $VenvPy -m pip install -r requirements.txt -q --disable-pip-version-check
Stop-Step $sw

# Real Chrome for the agent's browser tools (Playwright). Best-effort.
$sw = Start-Step "Installing the agent's Chrome browser"
try { & $VenvPy -m playwright install chromium 2>$null | Out-Null } catch {}
Stop-Step $sw

# --- frontend (ALWAYS rebuild so `agentstudio update` actually ships new UI) -
Set-Location (Join-Path $Dest "frontend")
if ($HasNode) {
  $sw = Start-Step "Building the user interface"
  npm install --silent
  npm run build
  Stop-Step $sw
} else {
  Write-Host "  Note: Node.js not found - using the prebuilt UI if present. Install Node.js + run 'agentstudio update' to rebuild." -ForegroundColor DarkGray
}

# --- install the `agentstudio` command --------------------------------------
$sw = Start-Step "Installing the 'agentstudio' command"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
Copy-Item (Join-Path $Dest "bin\agentstudio.cmd") (Join-Path $BinDir "agentstudio.cmd") -Force
$alias = ""
if (-not (Get-Command agent -ErrorAction SilentlyContinue)) {
  Copy-Item (Join-Path $Dest "bin\agentstudio.cmd") (Join-Path $BinDir "agent.cmd") -Force
  $alias = "  (short alias also works: agent run)"
}
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$BinDir*") {
  [Environment]::SetEnvironmentVariable("Path", "$userPath;$BinDir", "User")
}
Stop-Step $sw
Write-Progress -Activity "Installing Agent Studio" -Completed

Write-Host ""
Write-Host "  +========================================================+" -ForegroundColor Green
Write-Host "  |   OK All set!  Open a NEW terminal and run:             |" -ForegroundColor Green
Write-Host "  |                                                        |" -ForegroundColor Green
Write-Host "  |        agentstudio run                                 |" -ForegroundColor Green
Write-Host "  +========================================================+" -ForegroundColor Green
if ($alias) { Write-Host "  $alias" -ForegroundColor DarkGray }
Write-Host ""
