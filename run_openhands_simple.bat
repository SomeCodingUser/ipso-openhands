@echo off
REM OpenHands with WorktreeRuntime (V0 Legacy Server)
REM This bypasses the V1 app_server/agent_server architecture

REM Load environment from .env file if it exists
if exist ".env" (
    for /f "usebackq tokens=*" %%a in (".env") do (
        echo %%a | findstr /b "#" >nul || set "%%a"
    )
)

REM Set defaults
if "%RUNTIME%"=="" set RUNTIME=worktree
if "%BACKEND_HOST%"=="" set BACKEND_HOST=127.0.0.1
if "%BACKEND_PORT%"=="" set BACKEND_PORT=3000
if "%FRONTEND_PORT%"=="" set FRONTEND_PORT=3001

echo ============================================
echo OpenHands with WorktreeRuntime
echo ============================================
echo RUNTIME=%RUNTIME%
echo BACKEND_HOST=%BACKEND_HOST%
echo BACKEND_PORT=%BACKEND_PORT%
echo.

REM Build frontend if not exists
if not exist "frontend\build\index.html" (
    echo Building frontend...
    cd frontend
    call npm install
    call npm run build
    cd ..
)

REM Kill any existing processes on these ports
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%BACKEND_PORT%"') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%FRONTEND_PORT%"') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM Start Backend (V0 Legacy Server - directly uses WorktreeRuntime)
echo Starting backend (V0 Legacy Server)...
start "OpenHands Backend" cmd /k "set RUNTIME=%RUNTIME%&& uv run uvicorn openhands.server.listen:app --host %BACKEND_HOST% --port %BACKEND_PORT%"

REM Wait for backend
echo Waiting for backend...
timeout /t 10 /nobreak >nul

REM Start Frontend
echo Starting frontend...
start "OpenHands Frontend" cmd /k "cd frontend&& set VITE_BACKEND_HOST=%BACKEND_HOST%:%BACKEND_PORT%&& npm run dev -- --port %FRONTEND_PORT% --host %BACKEND_HOST%"

REM Wait for frontend
timeout /t 10 /nobreak >nul

REM Open browser
start http://%BACKEND_HOST%:%FRONTEND_PORT%

echo.
echo ============================================
echo OpenHands is running!
echo Backend: http://%BACKEND_HOST%:%BACKEND_PORT%
echo Frontend: http://%BACKEND_HOST%:%FRONTEND_PORT%
echo ============================================
echo.
echo NOTE: Using V0 Legacy Server with WorktreeRuntime
echo (bypasses V1 app_server/agent_server architecture)
echo.
echo Close the backend and frontend windows to stop.
pause
