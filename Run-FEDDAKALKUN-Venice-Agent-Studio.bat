@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "PY_EXE=%ROOT%.venv\Scripts\python.exe"
if not exist "%PY_EXE%" (
  echo [ERROR] Local venv not found.
  echo Run Install-FEDDAKALKUN-Venice-Agent-Studio.bat first.
  pause
  exit /b 1
)

set "PORT=7870"
echo Starting FEDDAKALKUN Venice Agent Studio...
echo URL: http://127.0.0.1:%PORT%
start "" "http://127.0.0.1:%PORT%"
"%PY_EXE%" "%ROOT%app.py"
pause
