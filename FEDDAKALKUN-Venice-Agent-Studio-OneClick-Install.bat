@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "REPO_URL=https://github.com/Feddakalkun/fedda-venice-api.git"
set "APP_DIR=FEDDAKALKUN-Venice-Agent-Studio"
set "ROOT=%~dp0"
cd /d "%ROOT%"

echo ==================================================
echo  FEDDAKALKUN Venice Agent Studio - OneClick Install
echo ==================================================
echo.

where git >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Git for Windows was not found.
  echo.
  echo Please install Git first:
  echo https://git-scm.com/download/win
  echo.
  echo Then run this installer again.
  pause
  exit /b 1
)

if exist "%APP_DIR%\.git" (
  echo Existing git install found.
  cd /d "%ROOT%%APP_DIR%"
  echo Pulling latest files...
  git pull --ff-only
  if errorlevel 1 goto :fail
) else (
  if exist "%APP_DIR%" (
    echo [ERROR] A folder named "%APP_DIR%" already exists, but it is not a git install.
    echo Rename or remove that folder, then run this installer again.
    pause
    exit /b 1
  )

  echo Downloading app from GitHub...
  git clone "%REPO_URL%" "%APP_DIR%"
  if errorlevel 1 goto :fail
  cd /d "%ROOT%%APP_DIR%"
)

echo.
echo Running app setup...
call "Install-FEDDAKALKUN-Venice-Agent-Studio.bat"
if errorlevel 1 goto :fail

echo.
echo [DONE] App installed.
echo.
echo To start later, open:
echo %ROOT%%APP_DIR%\Run-FEDDAKALKUN-Venice-Agent-Studio.bat
pause
exit /b 0

:fail
echo.
echo [ERROR] OneClick install failed.
pause
exit /b 1
