#!/bin/bash
# OpenHands WSL Setup Script
# This sets up OpenHands to run in WSL with WorktreeRuntime

set -e

echo "=========================================="
echo "OpenHands WSL Setup"
echo "=========================================="
echo ""

# Check if running in WSL
if ! grep -q Microsoft /proc/version 2>/dev/null && ! grep -q WSL /proc/version 2>/dev/null; then
    echo "ERROR: This script must be run inside WSL!"
    echo "Please open a WSL terminal and run:"
    echo "  bash setup_wsl.sh"
    exit 1
fi

echo "[1/6] Updating package lists..."
sudo apt-get update -qq

echo "[2/6] Installing prerequisites..."
sudo apt-get install -y -qq git curl build-essential python3 python3-pip python3-venv 2>/dev/null || true

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "[3/6] Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "[3/6] uv already installed"
fi

# Check if Node.js is installed (needs >= 20.19)
if ! command -v node &> /dev/null || [ "$(node -v | cut -d'v' -f2 | cut -d'.' -f1)" -lt 20 ]; then
    echo "[4/6] Installing Node.js 22..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt-get install -y nodejs
else
    echo "[4/6] Node.js already installed: $(node -v)"
fi

# Check if Docker is installed (optional but recommended)
if command -v docker &> /dev/null; then
    echo "[5/6] Docker found: $(docker --version)"
else
    echo "[5/6] Docker not found (optional - WorktreeRuntime doesn't require it)"
fi

echo "[6/6] Setup complete!"
echo ""
echo "=========================================="
echo "Next steps:"
echo "=========================================="
echo ""
echo "1. Clone your repository (if not already done):"
echo "   git clone https://github.com/SomeCodingUser/ipso-openhands.git"
echo "   cd ipso-openhands"
echo ""
echo "2. Install Python dependencies:"
echo "   uv sync --locked"
echo ""
echo "3. Install frontend dependencies:"
echo "   cd frontend && npm install && npm run build && cd .."
echo ""
echo "4. Create environment file:"
echo "   echo 'OH_SECRET_KEY=$(openssl rand -hex 32)' > .env"
echo "   echo 'RUNTIME=worktree' >> .env"
echo ""
echo "5. Run the application:"
echo "   bash run_wsl.sh"
echo ""
echo "=========================================="
