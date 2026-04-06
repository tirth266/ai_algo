@echo off
echo ============================================
echo ALGORITHMIC TRADING PLATFORM - STARTUP
echo ============================================

REM Move to project root
cd /d %~dp0\..

echo.
echo [1/3] Checking Python...

python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Python is not installed
    pause
    exit /b
)

echo Python found

echo.
echo [2/3] Starting Backend (Flask)...

cd backend

start cmd /k "python app.py"

echo Backend started on http://localhost:7000

cd ..

echo.
echo [3/3] Starting Frontend...

cd frontend

IF EXIST "node_modules" (
    start cmd /k "npm run dev"
) ELSE (
    echo Installing dependencies...
    npm install
    start cmd /k "npm run dev"
)

echo Frontend started (Vite)

cd ..

echo.
echo Platform is running!
echo Backend: http://localhost:7000
echo Frontend: http://localhost:5173

pause