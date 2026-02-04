@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM ============================================
REM OpenHands with WorktreeRuntime Launcher
REM ============================================

echo.
echo ============================================
echo    OpenHands with WorktreeRuntime
echo    Docker-free using git worktrees
echo ============================================
echo.

REM Configuration
set RUNTIME=worktree
set BACKEND_HOST=127.0.0.1
set BACKEND_PORT=3000
set FRONTEND_PORT=3001

echo [CONFIG] RUNTIME=%RUNTIME%
echo.

REM Check if uv is available
where uv >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] uv not found. Please install uv first:
    echo   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    pause
    exit /b 1
)

REM Check if npm is available
where npm >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] npm not found. Please install Node.js 20.19+ or 22.12+ first.
    pause
    exit /b 1
)

REM Check if frontend is built
if not exist "frontend\build\index.html" (
    echo [WARNING] Frontend build not found. Building now...
    echo.
    cd frontend
    call npm install
    call npm run build
    cd ..
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Frontend build failed.
        pause
        exit /b 1
    )
)

echo [INFO] Starting OpenHands...
echo [INFO] Backend: http://%BACKEND_HOST%:%BACKEND_PORT%
echo [INFO] Frontend: http://%BACKEND_HOST%:%FRONTEND_PORT%
echo [INFO] Runtime: %RUNTIME%
echo.

REM Kill any existing processes on these ports
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%BACKEND_PORT%"') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%FRONTEND_PORT%"') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM Start Backend - no space before && to avoid trailing space in variable
echo [1/3] Starting backend server...
start "OpenHands Backend" cmd /k "set RUNTIME=worktree&& uv run uvicorn openhands.server.listen:app --host %BACKEND_HOST% --port %BACKEND_PORT%"

REM Wait for backend to start
echo [2/3] Waiting for backend to be ready...
:wait_backend
timeout /t 1 /nobreak >nul
powershell -Command "try { Invoke-WebRequest -Uri 'http://%BACKEND_HOST%:%BACKEND_PORT%' -Method GET -ErrorAction Stop ^| Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% neq 0 goto wait_backend
echo      Backend is ready!

REM Start Frontend - no space before && to avoid trailing space in variable
echo [3/3] Starting frontend server...
start "OpenHands Frontend" cmd /k "cd frontend&& set VITE_BACKEND_HOST=%BACKEND_HOST%:%BACKEND_PORT%&& npm run dev -- --port %FRONTEND_PORT% --host %BACKEND_HOST%"

REM Wait for frontend
echo [3/3] Waiting for frontend to be ready...
:wait_frontend
timeout /t 1 /nobreak >nul
powershell -Command "try { Invoke-WebRequest -Uri 'http://%BACKEND_HOST%:%FRONTEND_PORT%' -Method GET -ErrorAction Stop ^| Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% neq 0 goto wait_frontend
echo      Frontend is ready!

echo.
echo ============================================
echo   OpenHands is running!
echo   Backend:  http://%BACKEND_HOST%:%BACKEND_PORT%
echo   Frontend: http://%BACKEND_HOST%:%FRONTEND_PORT%
echo ============================================
echo.

REM Open browser
start http://%BACKEND_HOST%:%FRONTEND_PORT%

echo Press any key to stop all servers...
pause >nul

REM Kill processes
echo.
echo [INFO] Stopping servers...
taskkill /F /FI "WINDOWTITLE eq OpenHands Backend" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq OpenHands Frontend" >nul 2>&1
echo [INFO] Servers stopped.

echo.
pause
