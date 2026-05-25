@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "ROOT=%~dp0"
cd /d "%ROOT%"
set "REPO_URL=https://github.com/Feddakalkun/fedda-venice-api.git"
set "APP_DIR=FEDDAKALKUN-Venice-Agent-Studio"
set "APP_ROOT=%ROOT%"
set "PIP_FLAGS=--disable-pip-version-check --no-input --progress-bar off -q"
set "DO_UPGRADE_TOOLS=0"
if /I "%FEDDA_VERBOSE%"=="1" set "PIP_FLAGS="
if /I "%FEDDA_UPGRADE_TOOLS%"=="1" set "DO_UPGRADE_TOOLS=1"
for %%I in ("%ROOT:~0,-1%") do set "ROOT_NAME=%%~nxI"

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

    if exist "%ROOT%\.git" (
      echo Existing app repo found. Pulling latest files...
      set "APP_ROOT=%ROOT%"
      cd /d "%APP_ROOT%"
      git pull --ff-only
      if errorlevel 1 goto :fail
    ) else (
      set "CLONE_TARGET=%ROOT%%APP_DIR%"
      set "CLONE_TMP_MODE=0"
      if /I "%ROOT_NAME%"=="%APP_DIR%" (
        set "CLONE_TARGET=%ROOT%__repo_tmp__"
        set "CLONE_TMP_MODE=1"
      )
      if exist "%CLONE_TARGET%" (
        echo [ERROR] Folder "%CLONE_TARGET%" already exists.
        echo Rename/delete that folder and run installer again.
        pause
        exit /b 1
      )
      echo Downloading app files from GitHub...
      git clone "%REPO_URL%" "%CLONE_TARGET%"
      if errorlevel 1 goto :fail

      if "%CLONE_TMP_MODE%"=="1" (
        echo Moving downloaded app files into current folder...
        robocopy "%CLONE_TARGET%" "%ROOT%" /E >nul
        if errorlevel 8 goto :fail
        rmdir /s /q "%CLONE_TARGET%"
        set "APP_ROOT=%ROOT%"
      ) else (
        set "APP_ROOT=%CLONE_TARGET%\"
      )
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

if "%DO_UPGRADE_TOOLS%"=="1" (
  echo Upgrading pip/setuptools/wheel...
  "%PY_EXE%" -m pip install %PIP_FLAGS% --upgrade pip wheel setuptools
  if errorlevel 1 goto :fail
) else (
  echo Skipping pip/setuptools/wheel upgrade. Set FEDDA_UPGRADE_TOOLS=1 to enable.
)

echo Installing requirements...
"%PY_EXE%" -m pip install %PIP_FLAGS% -r "%ROOT%requirements.txt"
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
