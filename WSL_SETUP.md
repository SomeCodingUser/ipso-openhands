# OpenHands WSL Setup Guide

This guide explains how to run OpenHands with WorktreeRuntime on Windows using WSL (Windows Subsystem for Linux).

## Why WSL?

The OpenHands V1 architecture requires Linux-specific features (`fcntl` module) that don't exist on Windows. WSL provides a full Linux environment where everything works correctly.

## Prerequisites

1. **Windows 10/11** with WSL2 installed
2. **WSL2** with a Linux distribution (Ubuntu recommended)

### Install WSL (if not already installed)

Open PowerShell as Administrator and run:

```powershell
wsl --install
```

Restart your computer, then set up your Linux user when prompted.

## Setup Steps

### 1. Open WSL Terminal

Open your WSL terminal (e.g., Ubuntu) from the Start menu or run:

```powershell
wsl
```

### 2. Navigate to the Project

Assuming you have the project on your Windows C: drive:

```bash
cd /mnt/c/Data/Projects/OpenHands
```

Or clone fresh:

```bash
cd ~
git clone https://github.com/SomeCodingUser/ipso-openhands.git
cd ipso-openhands
```

### 3. Run Setup Script

```bash
bash setup_wsl.sh
```

This will install:
- Python 3 and build tools
- uv (Python package manager)
- Node.js 22

### 4. Install Dependencies

```bash
# Install Python dependencies
uv sync --locked

# Install and build frontend
cd frontend
npm install
npm run build
cd ..
```

### 5. Create Environment File

```bash
echo "OH_SECRET_KEY=$(openssl rand -hex 32)" > .env
echo "RUNTIME=worktree" >> .env
```

### 6. Run OpenHands

```bash
bash run_wsl.sh
```

## Accessing from Windows

Once running in WSL, you can access OpenHands from Windows:

- **Frontend**: http://localhost:3001
- **Backend**: http://localhost:3000

The WSL network is automatically shared with Windows.

## Troubleshooting

### Port Already in Use

If you get "address already in use" errors:

```bash
# Kill existing processes
pkill -f uvicorn
pkill -f "npm run dev"
```

Then run `run_wsl.sh` again.

### Windows Defender/Firewall

If you can't access from Windows, check Windows Defender:

1. Open Windows Security
2. Firewall & network protection
3. Allow an app through firewall
4. Add WSL

### File Permissions

If you get permission errors:

```bash
# Fix permissions
sudo chown -R $(whoami):$(whoami) .
```

## Differences from Windows Native

| Feature | Windows Native | WSL |
|---------|---------------|-----|
| WorktreeRuntime | ✅ Works | ✅ Works |
| V1 Conversations | ❌ Broken | ✅ Works |
| Docker | ❌ Not needed | Optional |
| fcntl | ❌ Not available | ✅ Available |
| Performance | Native | Very close to native |

## Updating Code

When you update code from Windows, the changes are immediately visible in WSL since WSL can access Windows files at `/mnt/c/`.

## Alternative: Pure WSL Install

For better performance, you can keep the project entirely in WSL:

```bash
cd ~
git clone https://github.com/SomeCodingUser/ipso-openhands.git
cd ipso-openhands
# Follow setup steps above
```

This avoids any Windows filesystem overhead.
