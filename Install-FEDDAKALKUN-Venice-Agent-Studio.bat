@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "ROOT=%~dp0"
cd /d "%ROOT%"
set "REPO_URL=https://github.com/Feddakalkun/fedda-venice-api.git"
set "APP_DIR=FEDDAKALKUN-Venice-Agent-Studio"
set "APP_ROOT=%ROOT%"

if not exist "%ROOT%requirements.txt" (
  if not exist "%ROOT%app.py" (
    echo [WARN] App files not found next to this installer.
    echo.
    where git >nul 2>nul
    if errorlevel 1 (
      echo [ERROR] Git for Windows was not found.
      echo Install Git first: https://git-scm.com/download/win
      pause
      exit /b 1
    )

    if exist "%ROOT%%APP_DIR%\.git" (
      echo Existing app repo found. Pulling latest files...
      set "APP_ROOT=%ROOT%%APP_DIR%\"
      cd /d "%APP_ROOT%"
      git pull --ff-only
      if errorlevel 1 goto :fail
    ) else (
      if exist "%ROOT%%APP_DIR%" (
        echo [ERROR] Folder "%ROOT%%APP_DIR%" exists but is not a git checkout.
        echo Rename/delete that folder and run installer again.
        pause
        exit /b 1
      )
      echo Downloading app files from GitHub...
      git clone "%REPO_URL%" "%ROOT%%APP_DIR%"
      if errorlevel 1 goto :fail
      set "APP_ROOT=%ROOT%%APP_DIR%\"
      cd /d "%APP_ROOT%"
    )
    set "ROOT=%APP_ROOT%"
  ) else (
    echo [ERROR] requirements.txt is missing in:
    echo %ROOT%
    echo Make sure all app files are in the same folder as this installer.
    pause
    exit /b 1
  )
)

if not exist "%ROOT%requirements.txt" (
  if exist "%APP_ROOT%requirements.txt" set "ROOT=%APP_ROOT%"
)

if not exist "%ROOT%requirements.txt" (
  echo [ERROR] requirements.txt was not found after setup path resolution.
  echo Expected path:
  echo %ROOT%requirements.txt
  pause
  exit /b 1
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
