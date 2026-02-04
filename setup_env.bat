@echo off
REM Setup script for OpenHands WorktreeRuntime on Windows

echo ============================================
echo OpenHands Environment Setup
echo ============================================
echo.

REM Check if .env already exists
if exist ".env" (
    echo .env file already exists.
    set /p overwrite="Overwrite? (y/n): "
    if /i not "%overwrite%"=="y" exit /b 0
)

REM Generate random secret key
echo Generating OH_SECRET_KEY...
for /f "tokens=*" %%a in ('python -c "import secrets; print(secrets.token_hex(32))"') do set SECRET_KEY=%%a

REM Create .env file
echo Creating .env file...
(
echo # OpenHands Environment Variables
echo # Generated for Windows WorktreeRuntime setup
echo.
echo # Required: Secret key for encrypting sensitive data
(echo OH_SECRET_KEY=%SECRET_KEY%)
echo.
echo # Runtime configuration (worktree = no docker needed)
echo RUNTIME=worktree
echo.
echo # Backend configuration
echo BACKEND_HOST=127.0.0.1
echo BACKEND_PORT=3000
echo.
echo # Optional: GitHub token for repository access
echo # GITHUB_TOKEN=your_token_here
) > .env

echo.
echo ============================================
echo Setup complete!
echo.
echo Environment file created: .env
echo.
echo You can now run: run_openhands_simple.bat
echo ============================================
pause
