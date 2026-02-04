#!/bin/bash
# OpenHands Runner for WSL with WorktreeRuntime

set -e

echo "=========================================="
echo "OpenHands with WorktreeRuntime (WSL)"
echo "=========================================="
echo ""

# Load environment from .env if exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Set defaults
export RUNTIME=${RUNTIME:-worktree}
export BACKEND_HOST=${BACKEND_HOST:-127.0.0.1}
export BACKEND_PORT=${BACKEND_PORT:-3000}
export FRONTEND_PORT=${FRONTEND_PORT:-3001}

echo "Configuration:"
echo "  RUNTIME: $RUNTIME"
echo "  BACKEND_HOST: $BACKEND_HOST"
echo "  BACKEND_PORT: $BACKEND_PORT"
echo "  FRONTEND_PORT: $FRONTEND_PORT"
echo ""

# Generate secret key if not set
if [ -z "$OH_SECRET_KEY" ]; then
    echo "Generating OH_SECRET_KEY..."
    export OH_SECRET_KEY=$(openssl rand -hex 32)
    echo "OH_SECRET_KEY=$OH_SECRET_KEY" >> .env
fi

# Build frontend if needed
if [ ! -f "frontend/build/index.html" ]; then
    echo "Building frontend..."
    cd frontend
    npm install
    npm run build
    cd ..
fi

# Kill existing processes
echo "Cleaning up existing processes..."
pkill -f "uvicorn.*openhands.server" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true
sleep 2

echo ""
echo "Starting OpenHands..."
echo ""

# Start backend in background
echo "[1/2] Starting backend server..."
uv run uvicorn openhands.server.listen:app --host $BACKEND_HOST --port $BACKEND_PORT &
BACKEND_PID=$!

# Wait for backend
echo "Waiting for backend..."
for i in {1..30}; do
    if curl -s http://$BACKEND_HOST:$BACKEND_PORT/health > /dev/null 2>&1; then
        echo "  Backend ready!"
        break
    fi
    sleep 1
done

# Start frontend in background
echo "[2/2] Starting frontend server..."
cd frontend
VITE_BACKEND_HOST=$BACKEND_HOST:$BACKEND_PORT npm run dev -- --port $FRONTEND_PORT --host $BACKEND_HOST &
FRONTEND_PID=$!
cd ..

# Wait for frontend
echo "Waiting for frontend..."
for i in {1..30}; do
    if curl -s http://$BACKEND_HOST:$FRONTEND_PORT > /dev/null 2>&1; then
        echo "  Frontend ready!"
        break
    fi
    sleep 1
done

echo ""
echo "=========================================="
echo "OpenHands is running!"
echo "=========================================="
echo ""
echo "Backend:  http://$BACKEND_HOST:$BACKEND_PORT"
echo "Frontend: http://$BACKEND_HOST:$FRONTEND_PORT"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Open browser (if xdg-open is available)
if command -v xdg-open &> /dev/null; then
    xdg-open http://$BACKEND_HOST:$FRONTEND_PORT 2>/dev/null || true
fi

# Wait for interrupt
trap "echo ''; echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT
wait
