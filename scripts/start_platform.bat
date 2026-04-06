@echo off
echo ============================================
echo ALGORITHMIC TRADING PLATFORM - STARTUP
echo ============================================

REM Go to project root
cd /d %~dp0\..

echo.
echo [1/4] Checking Docker...

docker --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Docker is not installed or not running
    pause
    exit /b
)

echo Docker is running

echo.
echo [2/4] Checking .env file...

IF NOT EXIST ".env" (
    echo .env file not found
    pause
    exit /b
)

echo .env found

echo.
echo [3/4] Building Docker containers...

docker-compose build

IF %ERRORLEVEL% NEQ 0 (
    echo Build failed
    pause
    exit /b
)

echo.
echo [4/4] Starting platform...

docker-compose up

echo.
echo Platform started successfully!
pause