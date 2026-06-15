@echo off
REM Agent Studio - one-click launcher for Windows (double-click this file).
REM First run sets up anything missing, then starts the app and opens it in
REM your browser. Python-only when the UI is prebuilt.
setlocal enableextensions
cd /d "%~dp0"

echo.
echo   ============================================================
echo      AGENT STUDIO   ^|   Windows Launcher
echo   ============================================================
echo.

REM --- pick a Python 3.10+ ---
set "PY="
py -3 -c "import sys;raise SystemExit(0 if sys.version_info[:2]>=(3,10) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys;raise SystemExit(0 if sys.version_info[:2]>=(3,10) else 1)" >nul 2>nul && set "PY=python"
if not defined PY (
  echo   [ERROR] Python 3.10+ not found.
  echo   Install from https://www.python.org/downloads/  ^(tick "Add python.exe to PATH"^).
  pause & exit /b 1
)
echo   [1/4] Python OK

REM --- backend venv + packages ---
echo   [2/4] Preparing backend...
if not exist "backend\venv\Scripts\python.exe" (
  echo         Creating virtual environment...
  %PY% -m venv backend\venv || ( echo   [ERROR] Could not create venv. & pause & exit /b 1 )
)
set "VENV_PY=%~dp0backend\venv\Scripts\python.exe"
"%VENV_PY%" -c "import uvicorn, fastapi, openai, sqlalchemy, pypdf, fpdf, lxml, bs4, requests, playwright" >nul 2>nul
if errorlevel 1 (
  echo         Installing backend packages (first run, ~30s)...
  "%VENV_PY%" -m pip install --upgrade pip -q --disable-pip-version-check
  "%VENV_PY%" -m pip install -r backend\requirements.txt --disable-pip-version-check || ( echo   [ERROR] pip install failed (check internet). & pause & exit /b 1 )
) else (
  echo         Backend packages already installed.
)
REM Ensure the agent's Chrome (Playwright) is present - fast no-op when installed.
"%VENV_PY%" -m playwright install chromium >nul 2>nul
echo         OK

REM --- user interface ---
echo   [3/4] Preparing user interface...
if exist "frontend\dist\index.html" (
  echo         Prebuilt UI found - skipping Node setup.
) else (
  where node >nul 2>nul || ( echo   [ERROR] Node.js not found and no prebuilt UI. Install from https://nodejs.org & pause & exit /b 1 )
  pushd frontend
  if not exist node_modules ( echo         npm install ^(~60s^)... & call npm install || ( popd & pause & exit /b 1 ) )
  echo         Building ^(~30s^)...
  call npm run build || ( echo   [ERROR] Build failed (see above). & popd & pause & exit /b 1 )
  popd
)
echo         OK

REM --- free port 8000, then start ---
echo   [4/4] Starting server...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do taskkill /F /PID %%P >nul 2>nul

REM Open the browser as soon as the server answers (background health poll).
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for($i=0;$i -lt 60;$i++){Start-Sleep -Seconds 1; try{ if((Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2).StatusCode -eq 200){ Start-Process 'http://127.0.0.1:8000'; break } }catch{} }"

echo.
echo   ============================================================
echo      AGENT STUDIO is starting at http://127.0.0.1:8000
echo      Your browser opens automatically when ready.
echo      To STOP: press Ctrl+C here, or close this window.
echo   ============================================================
echo.

cd backend
"%VENV_PY%" -m uvicorn main:app --host 127.0.0.1 --port 8000
