@echo off
REM Agent Studio - first-time setup for Windows (double-click this file).
REM Equivalent of install.command on macOS. START.bat does this too.
setlocal enableextensions
cd /d "%~dp0"

echo.
echo   ==========================================================
echo     AGENT STUDIO  ^|  First-Time Installation (Windows)
echo   ==========================================================
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
echo   [1/5] Python found. OK

REM 2) Node.js
where node >nul 2>nul || (
  echo   [ERROR] Node.js not found. Install from https://nodejs.org
  pause & exit /b 1
)
echo   [2/5] Node.js found. OK

REM 3) Python virtual environment
echo   [3/5] Creating Python virtual environment...
if exist "backend\venv\Scripts\python.exe" (
  echo         Already exists, skipping.
) else (
  %PY% -m venv backend\venv || ( echo   [ERROR] venv creation failed. & pause & exit /b 1 )
  echo         Created.
)
set "VENV_PY=%~dp0backend\venv\Scripts\python.exe"

REM 4) Backend packages
echo   [4/5] Installing backend packages (~30s)...
"%VENV_PY%" -m pip install --upgrade pip -q --disable-pip-version-check
"%VENV_PY%" -m pip install -r backend\requirements.txt --disable-pip-version-check || ( echo   [ERROR] pip install failed (check internet). & pause & exit /b 1 )
echo         Backend packages installed.

REM 5) Frontend
echo   [5/5] Installing and building the user interface (~60s)...
pushd frontend
call npm install || ( echo   [ERROR] npm install failed. & popd & pause & exit /b 1 )
call npm run build || ( echo   [ERROR] frontend build failed. & popd & pause & exit /b 1 )
popd
echo         User interface built.

echo.
echo   ==========================================================
echo     Installation COMPLETE!  Now double-click  run.bat
echo   ==========================================================
echo.
pause
