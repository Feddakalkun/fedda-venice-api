@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "ROOT=%~dp0"
cd /d "%ROOT%"

if exist "disclaimer.md" (
  type "disclaimer.md"
  pause
)

set "VENV=%ROOT%.venv"
set "PY_EXE=%VENV%\Scripts\python.exe"

echo ==========================================
echo  FEDDAKALKUN Venice Agent Studio - Setup
echo ==========================================
echo.

if not exist "%PY_EXE%" (
  echo Creating local Python virtual environment...
  py -3 -m venv "%VENV%"
  if errorlevel 1 (
    echo [ERROR] Could not create venv with py -3.
    pause
    exit /b 1
  )
)

echo Upgrading pip...
"%PY_EXE%" -m pip install --upgrade pip wheel setuptools
if errorlevel 1 goto :fail

echo Installing requirements...
"%PY_EXE%" -m pip install -r "%ROOT%requirements.txt"
if errorlevel 1 goto :fail

echo.
echo [DONE] Setup complete.
echo Run: Run-FEDDAKALKUN-Venice-Agent-Studio.bat
pause
exit /b 0

:fail
echo.
echo [ERROR] Setup failed.
pause
exit /b 1
