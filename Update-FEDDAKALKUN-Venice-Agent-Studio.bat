@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "ROOT=%~dp0"
cd /d "%ROOT%"

echo ==========================================
echo  FEDDAKALKUN Venice Agent Studio - Update
echo ==========================================
echo.

where git >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Git was not found on this computer.
  echo Install Git for Windows, then run this updater again:
  echo https://git-scm.com/download/win
  pause
  exit /b 1
)

if not exist ".git" (
  echo [ERROR] This folder is not a git checkout yet.
  echo.
  echo To use automatic updates, distribute this app from a git repository:
  echo   git clone https://github.com/Feddakalkun/fedda-venice-api.git FEDDAKALKUN-Venice-Agent-Studio
  echo.
  echo This updater will then pull the latest files from that repo.
  pause
  exit /b 1
)

echo Checking repository...
git remote -v
echo.

echo Pulling latest app files...
git pull --ff-only
if errorlevel 1 (
  echo.
  echo [ERROR] Update failed.
  echo If you modified app files locally, commit/stash them or reinstall from a fresh clone.
  pause
  exit /b 1
)

set "PY_EXE=%ROOT%.venv\Scripts\python.exe"
if exist "%PY_EXE%" (
  echo.
  echo Refreshing Python requirements...
  "%PY_EXE%" -m pip install -r "%ROOT%requirements.txt"
  if errorlevel 1 (
    echo [WARN] App files updated, but requirement refresh failed.
    echo Try running Install-FEDDAKALKUN-Venice-Agent-Studio.bat again.
    pause
    exit /b 1
  )
) else (
  echo.
  echo [INFO] No local venv found yet. Run the installer before launching.
)

echo.
echo [DONE] Update complete.
pause
exit /b 0
