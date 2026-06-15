@echo off
REM Agent Studio - first-time setup for Windows (double-click this file).
REM Equivalent of install.command on macOS. START.bat does this too.
setlocal enableextensions enabledelayedexpansion
cd /d "%~dp0"

echo.
echo   +========================================================+
echo   ^|   * AGENT STUDIO  -  First-Time Installation (Windows) ^|
echo   +========================================================+
echo   Setting things up - keep this window open, it takes a minute.
echo.

REM 1) Python 3.10+ (prefer the py launcher, then python)
set "PY="
py -3 -c "import sys;raise SystemExit(0 if sys.version_info[:2]>=(3,10) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys;raise SystemExit(0 if sys.version_info[:2]>=(3,10) else 1)" >nul 2>nul && set "PY=python"
if not defined PY (
  echo   [ERROR] Python 3.10+ not found.
  echo   Install from https://www.python.org/downloads/  ^(tick "Add python.exe to PATH"^).
  pause & exit /b 1
)
where node >nul 2>nul || (
  echo   [ERROR] Node.js not found. Install from https://nodejs.org
  pause & exit /b 1
)
echo   * Python and Node.js found.
echo.

set "VENV_PY=%~dp0backend\venv\Scripts\python.exe"

echo   -^> [1/4] Creating the Python environment ...
if not exist "backend\venv\Scripts\python.exe" (
  %PY% -m venv backend\venv || ( echo   [ERROR] venv creation failed. & pause & exit /b 1 )
)
"%VENV_PY%" -m pip install --upgrade pip -q --disable-pip-version-check
call :bar 25

echo   -^> [2/4] Installing backend packages ...
"%VENV_PY%" -m pip install -r backend\requirements.txt -q --disable-pip-version-check || ( echo   [ERROR] pip install failed (check internet). & pause & exit /b 1 )
call :bar 50

echo   -^> [3/4] Installing the agent's Chrome browser ...
"%VENV_PY%" -m playwright install chromium >nul 2>nul || echo         (Chromium download deferred; the agent will retry on first use.)
call :bar 75

echo   -^> [4/4] Building the user interface ...
pushd frontend
call npm install --silent || ( echo   [ERROR] npm install failed. & popd & pause & exit /b 1 )
call npm run build || ( echo   [ERROR] frontend build failed. & popd & pause & exit /b 1 )
popd
call :bar 100

echo.
echo   +========================================================+
echo   ^|   OK Installation complete!  Double-click  run.bat     ^|
echo   +========================================================+
echo.
pause
exit /b 0

REM ── progress bar: call :bar ^<percent^> ───────────────────────────────────
:bar
set /a _pct=%1
set /a _fill=_pct/5
set "_b="
for /l %%i in (1,1,20) do (
  if %%i leq !_fill! (set "_b=!_b!#") else (set "_b=!_b!-")
)
echo      [!_b!] !_pct!%%
echo.
goto :eof
