@echo off
REM Simple OpenHands with WorktreeRuntime Launcher

set RUNTIME=worktree
set BACKEND_HOST=127.0.0.1
set BACKEND_PORT=3000
set FRONTEND_PORT=3001

echo Starting OpenHands with WorktreeRuntime...
echo RUNTIME=%RUNTIME%
echo.

REM Build frontend if not exists
if not exist "frontend\build\index.html" (
    echo Building frontend...
    cd frontend
    call npm install
    call npm run build
    cd ..
)

REM Start Backend in new window - worktree uses ProcessSandbox automatically
echo Starting backend...
start "OpenHands Backend" cmd /k "set RUNTIME=worktree&& uv run uvicorn openhands.server.listen:app --host 127.0.0.1 --port 3000"

REM Wait for backend
echo Waiting for backend...
timeout /t 10 /nobreak >nul

REM Start Frontend in new window
echo Starting frontend...
start "OpenHands Frontend" cmd /k "cd frontend&& set VITE_BACKEND_HOST=127.0.0.1:3000&& npm run dev -- --port 3001 --host 127.0.0.1"

REM Wait for frontend
echo Waiting for frontend...
timeout /t 10 /nobreak >nul

REM Open browser
start http://127.0.0.1:3001

echo.
echo OpenHands is running!
echo Backend: http://127.0.0.1:3000
echo Frontend: http://127.0.0.1:3001
echo.
echo Close the backend and frontend windows to stop the servers.
pause
