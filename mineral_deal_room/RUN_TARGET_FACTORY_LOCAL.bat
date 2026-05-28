@echo off
title DOTO Mineral Deal Intelligence Room - Target Factory v1
color 0A

echo ============================================================
echo  DataBossX - Mineral Deal Intelligence Room
echo  Target Factory v1
echo  LOCAL INSTANCE - No cloud, no uploads
echo ============================================================
echo.

:: Change to the directory containing this .bat file
cd /d "%~dp0"

:: Log file
set LOGFILE=%~dp0install_log.txt
echo [%DATE% %TIME%] Launcher started >> "%LOGFILE%"

:: Check for Node.js
echo Checking for Node.js...
where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Node.js not found.
    echo Please install Node.js from https://nodejs.org ^(LTS version^)
    echo Then re-run this launcher.
    echo [%DATE% %TIME%] ERROR: Node.js not found >> "%LOGFILE%"
    pause
    exit /b 1
)

:: Show Node version
for /f "tokens=*" %%v in ('node --version') do set NODEVERSION=%%v
echo Node.js found: %NODEVERSION%
echo [%DATE% %TIME%] Node version: %NODEVERSION% >> "%LOGFILE%"

:: Install dependencies if node_modules is missing
if not exist "node_modules\" (
    echo.
    echo Installing dependencies ^(first run only - takes 1-2 minutes^)...
    echo [%DATE% %TIME%] Running npm install >> "%LOGFILE%"
    npm install >> "%LOGFILE%" 2>&1
    if %ERRORLEVEL% neq 0 (
        echo.
        echo ERROR: npm install failed. Check install_log.txt for details.
        echo [%DATE% %TIME%] npm install FAILED >> "%LOGFILE%"
        pause
        exit /b 1
    )
    echo Dependencies installed OK.
    echo [%DATE% %TIME%] npm install OK >> "%LOGFILE%"
) else (
    echo Dependencies already installed.
)

:: Launch the app
echo.
echo Starting Mineral Deal Intelligence Room...
echo URL: http://localhost:5173
echo.
echo Press Ctrl+C to stop the server.
echo.
echo [%DATE% %TIME%] Starting npm run dev >> "%LOGFILE%"

:: Open browser after short delay (in background)
start "" /b cmd /c "timeout /t 3 >nul && start http://localhost:5173"

:: Start Vite dev server
npm run dev

:: If we get here, the server stopped
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: App failed to start. Check install_log.txt for details.
    echo [%DATE% %TIME%] npm run dev FAILED with code %ERRORLEVEL% >> "%LOGFILE%"
    pause
    exit /b 1
)

echo [%DATE% %TIME%] Server stopped normally >> "%LOGFILE%"
pause
