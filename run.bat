@echo off
REM Agent Studio - start the app on Windows (double-click this file).
REM Assumes install.bat already ran; otherwise use START.bat.
setlocal enableextensions
cd /d "%~dp0"

set "VENV_PY=%~dp0backend\venv\Scripts\python.exe"
if not exist "%VENV_PY%" goto notready
if not exist "frontend\dist\index.html" goto notready

REM Free port 8000 if something is already listening (best-effort).
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do taskkill /F /PID %%P >nul 2>nul

REM Open the browser as soon as the server answers (background health poll).
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for($i=0;$i -lt 40;$i++){Start-Sleep -Seconds 1; try{ if((Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2).StatusCode -eq 200){ Start-Process 'http://127.0.0.1:8000'; break } }catch{} }"

echo.
echo   ==========================================================
echo     Agent Studio is starting at http://127.0.0.1:8000
echo     Your browser opens automatically when ready.
echo     To STOP: press Ctrl+C here, or close this window.
echo   ==========================================================
echo.

cd backend
"%VENV_PY%" -m uvicorn main:app --host 127.0.0.1 --port 8000
exit /b 0

:notready
echo.
echo   [ERROR] Setup is not complete.
echo   Double-click  install.bat  first  (or START.bat, which sets up everything).
echo.
pause
