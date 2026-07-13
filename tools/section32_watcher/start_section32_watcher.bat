@echo off
setlocal EnableExtensions

REM DataBossX Section 32 Watcher launcher. Sources remain read-only.
set "HERE=%~dp0"
set "CONFIG=%HERE%config.local.json"
set "LOGROOT=D:\DataBoss\Section32_Watcher\logs"

if not exist "%LOGROOT%" mkdir "%LOGROOT%"

where py >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python launcher "py" was not found.
  exit /b 10
)

if not exist "%CONFIG%" (
  echo ERROR: Missing %CONFIG%
  echo Copy config.example.json to config.local.json and set:
  echo   DBX_DROPBOX_SECTION32 = local Dropbox sync folder for 11N 25W 32
  echo   DBX_GDRIVE_SECTION32 = local Google Drive sync folder for the Section 32 project
  exit /b 11
)

if "%DBX_DROPBOX_SECTION32%"=="" (
  echo ERROR: DBX_DROPBOX_SECTION32 is not set.
  exit /b 12
)
if "%DBX_GDRIVE_SECTION32%"=="" (
  echo ERROR: DBX_GDRIVE_SECTION32 is not set.
  exit /b 13
)

for /f "tokens=1-4 delims=/ " %%a in ('date /t') do set "STAMP=%%d%%b%%c"
set "LOGFILE=%LOGROOT%\watcher_%STAMP%.log"

echo Starting Section 32 watcher...
echo Dropbox source: %DBX_DROPBOX_SECTION32%
echo Drive source:   %DBX_GDRIVE_SECTION32%
echo Log:            %LOGFILE%

py -3 "%HERE%watcher.py" --config "%CONFIG%" >> "%LOGFILE%" 2>&1
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" echo Watcher exited with code %RC%. Review %LOGFILE%
exit /b %RC%
