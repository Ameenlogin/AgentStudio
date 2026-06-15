@echo off
REM Agent Studio command-line launcher (Windows). Installed as `agentstudio`
REM (and `agent` if that name is free). Usage: agentstudio [run|install|stop]
setlocal
if "%AGENT_STUDIO_HOME%"=="" (set "REPO=%USERPROFILE%\AgentStudio") else (set "REPO=%AGENT_STUDIO_HOME%")

if not exist "%REPO%" (
  echo Agent Studio is not installed at %REPO%.
  echo Install it with this command in PowerShell:
  echo   irm https://raw.githubusercontent.com/Ameenlogin/AgentStudio/main/install.ps1 ^| iex
  exit /b 1
)

set "ACT=%~1"
if "%ACT%"=="" set "ACT=run"
if /i "%ACT%"=="run"     goto run
if /i "%ACT%"=="start"   goto run
if /i "%ACT%"=="install" goto upd
if /i "%ACT%"=="update"  goto upd
if /i "%ACT%"=="upgrade" goto upd
if /i "%ACT%"=="stop"    goto stop
echo Usage: agentstudio [run^|install^|stop]
exit /b 1

:run
call "%REPO%\run.bat"
exit /b

:upd
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO%\install.ps1"
exit /b

:stop
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do taskkill /F /PID %%P >nul 2>nul
echo Agent Studio stopped.
exit /b
