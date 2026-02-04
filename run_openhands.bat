@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM ============================================
REM OpenHands with WorktreeRuntime (Podman)
REM Backend: Linux Container | Frontend: Windows
REM ============================================

echo.
echo ============================================
echo    OpenHands with WorktreeRuntime
echo ============================================
echo.

set BACKEND_HOST=127.0.0.1
set BACKEND_PORT=3000
set FRONTEND_PORT=3001
set CONTAINER_NAME=openhands-worktree
set IMAGE_NAME=openhands-worktree:latest

echo [CONFIG] BACKEND:  http://%BACKEND_HOST%:%BACKEND_PORT%
echo [CONFIG] FRONTEND: http://%BACKEND_HOST%:%FRONTEND_PORT%
echo.

REM Check Podman
echo [CHECK] Checking Podman...
where podman >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Podman not found!
    echo.
    echo Install from: https://podman-desktop.io/downloads
    echo Then run: podman machine init ^&^& podman machine start
    echo.
    pause
    exit /b 1
)
podman --version
echo.

REM Generate/load secret key
if not exist ".env" (
    echo [SETUP] Generating secret key...
    powershell -Command "$key = -join ((1..64) | ForEach-Object { Get-Random -Maximum 16 | ForEach-Object { '{0:x}' -f $_ } }); Set-Content -Path '.env' -Value \"OH_SECRET_KEY=$key\"" >nul 2>&1
    echo [OK] Created .env file
)
for /f "usebackq tokens=*" %%a in (".env") do set "%%a"
echo [OK] Secret key loaded
echo.

REM Check npm
echo [CHECK] Checking npm...
where npm >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] npm not found. Install Node.js 20.19+
    pause
    exit /b 1
)
echo [OK] npm found
echo.

REM Build frontend if needed
if not exist "frontend\build\index.html" (
    echo [BUILD] Building frontend...
    cd frontend
    call npm install
    call npm run build
    cd ..
)
echo [OK] Frontend ready
echo.

REM Clean up ports
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%BACKEND_PORT%\":%FRONTEND_PORT%"') do taskkill /F /PID %%a >nul 2>&1

REM Check/restart container
echo [CHECK] Checking container...
podman ps --format "{{.Names}}" 2>nul | findstr /b "%CONTAINER_NAME%" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [INFO] Restarting existing container...
    podman stop %CONTAINER_NAME% >nul 2>&1
    podman rm %CONTAINER_NAME% >nul 2>&1
)

REM Build image if needed
podman image exists %IMAGE_NAME% >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [BUILD] Building container image...
    echo          (This may take a few minutes...)
    podman build -t %IMAGE_NAME% -f Containerfile .
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Build failed!
        pause
        exit /b 1
    )
    echo [OK] Image built
)

if not exist "workspace" mkdir workspace

REM Start backend container
echo.
echo [START] Starting backend in Podman container...
start "OpenHands Backend (Podman)" cmd /k "podman run -it --rm --name %CONTAINER_NAME% -p %BACKEND_PORT%:%BACKEND_PORT% -e RUNTIME=worktree -e BACKEND_HOST=0.0.0.0 -e BACKEND_PORT=%BACKEND_PORT% -e OH_SECRET_KEY=%OH_SECRET_KEY% -e PYTHONUNBUFFERED=1 -v ""%CD%\workspace:/workspace"" -v ""%USERPROFILE%\.gitconfig:/root/.gitconfig:ro"" %IMAGE_NAME%"

REM Wait for backend
echo.
echo [WAIT] Waiting for backend...
set /a count=0
:wait_backend
set /a count+=1
timeout /t 2 /nobreak >nul
if %count% gtr 60 goto backend_timeout
powershell -Command "try { Invoke-WebRequest -Uri 'http://%BACKEND_HOST%:%BACKEND_PORT%/health' -Method GET -TimeoutSec 2 -ErrorAction Stop ^| Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% neq 0 goto wait_backend
echo [OK] Backend ready!
goto backend_ready
:backend_timeout
echo [WARNING] Backend timeout, may still be starting...
:backend_ready

REM Start frontend
echo [START] Starting frontend on Windows...
start "OpenHands Frontend" cmd /k "cd frontend ^&^& set VITE_BACKEND_HOST=%BACKEND_HOST%:%BACKEND_PORT% ^&^& npm run dev -- --port %FRONTEND_PORT% --host %BACKEND_HOST%"

REM Wait for frontend
echo [WAIT] Waiting for frontend...
set /a count=0
:wait_frontend
set /a count+=1
timeout /t 2 /nobreak >nul
if %count% gtr 30 goto frontend_timeout
powershell -Command "try { Invoke-WebRequest -Uri 'http://%BACKEND_HOST%:%FRONTEND_PORT%' -Method GET -TimeoutSec 2 -ErrorAction Stop ^| Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% neq 0 goto wait_frontend
echo [OK] Frontend ready!
goto frontend_ready
:frontend_timeout
echo [WARNING] Frontend timeout, may still be starting...
:frontend_ready

echo.
echo ============================================
echo    OpenHands is running!
echo ============================================
echo.
echo    Backend:  http://%BACKEND_HOST%:%BACKEND_PORT% (Podman Linux)
echo    Frontend: http://%BACKEND_HOST%:%FRONTEND_PORT% (Windows)
echo.
echo    Features: WorktreeRuntime + V1 Conversations
echo.
echo ============================================
echo.

start http://%BACKEND_HOST%:%FRONTEND_PORT%

echo Press any key to stop...
pause >nul

echo.
echo [STOP] Stopping servers...
taskkill /F /FI "WINDOWTITLE eq OpenHands Frontend*" >nul 2>&1
podman stop %CONTAINER_NAME% >nul 2>&1
echo [OK] Stopped.
echo.
pause
