@echo off
REM OpenHands Simple Launcher (Podman + Windows)
REM Backend: Podman Linux Container | Frontend: Windows Native

echo Starting OpenHands with WorktreeRuntime...
echo.

set BACKEND_PORT=3000
set FRONTEND_PORT=3001
set CONTAINER_NAME=openhands-worktree
set IMAGE_NAME=openhands-worktree:latest

REM Generate secret key if needed
if not exist ".env" (
    powershell -Command "$k = -join ((1..64) | ForEach-Object { Get-Random -Maximum 16 | ForEach-Object { '{0:x}' -f $_ } }); "OH_SECRET_KEY=$k" | Out-File -FilePath '.env' -Encoding ASCII" >nul 2>&1
)
for /f "usebackq tokens=*" %%a in (".env") do set "%%a"

REM Build frontend if needed
if not exist "frontend\build\index.html" (
    echo Building frontend...
    cd frontend
    call npm install
    call npm run build
    cd ..
)

REM Clean up existing container
podman stop %CONTAINER_NAME% >nul 2>&1
podman rm %CONTAINER_NAME% >nul 2>&1

REM Build image if needed
podman image exists %IMAGE_NAME% >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Building container image...
    podman build -t %IMAGE_NAME% -f Containerfile .
)

REM Create workspace
if not exist "workspace" mkdir workspace

REM Start backend in Podman
echo Starting backend in Podman container...
start "OpenHands Backend" cmd /k "podman run -it --rm --name %CONTAINER_NAME% -p %BACKEND_PORT%:%BACKEND_PORT% -e RUNTIME=worktree -e BACKEND_HOST=0.0.0.0 -e BACKEND_PORT=%BACKEND_PORT% -e OH_SECRET_KEY=%OH_SECRET_KEY% -e PYTHONUNBUFFERED=1 -v ""%CD%\workspace:/workspace"" -v ""%USERPROFILE%\.gitconfig:/root/.gitconfig:ro"" %IMAGE_NAME%"

REM Wait for backend
timeout /t 15 /nobreak >nul

REM Start frontend on Windows
echo Starting frontend on Windows...
start "OpenHands Frontend" cmd /k "cd frontend ^&^& set VITE_BACKEND_HOST=127.0.0.1:%BACKEND_PORT% ^&^& npm run dev -- --port %FRONTEND_PORT% --host 127.0.0.1"

REM Wait for frontend
timeout /t 10 /nobreak >nul

REM Open browser
start http://127.0.0.1:%FRONTEND_PORT%

echo.
echo OpenHands is running!
echo Backend:  http://127.0.0.1:%BACKEND_PORT% (Podman Linux)
echo Frontend: http://127.0.0.1:%FRONTEND_PORT% (Windows)
echo.
echo Press any key to stop...
pause >nul

REM Stop everything
taskkill /F /FI "WINDOWTITLE eq OpenHands Frontend*" >nul 2>&1
podman stop %CONTAINER_NAME% >nul 2>&1
echo Stopped.
