#!/bin/bash
# Start script for OpenHands in Podman container

set -e

echo "=========================================="
echo "OpenHands Podman Container"
echo "=========================================="
echo ""

# Generate secret key if not provided
if [ -z "$OH_SECRET_KEY" ] || [ "$OH_SECRET_KEY" = "default_secret_change_in_production" ]; then
    export OH_SECRET_KEY=$(openssl rand -hex 32)
    echo "Generated OH_SECRET_KEY"
fi

echo "Configuration:"
echo "  RUNTIME: $RUNTIME"
echo "  BACKEND_HOST: $BACKEND_HOST"
echo "  BACKEND_PORT: $BACKEND_PORT"
echo "  FRONTEND_PORT: $FRONTEND_PORT"
echo ""

# Start backend in background
echo "[1/2] Starting backend server..."
uv run uvicorn openhands.server.listen:app --host $BACKEND_HOST --port $BACKEND_PORT &
BACKEND_PID=$!

# Wait for backend to be ready
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
echo "Backend:  http://localhost:$BACKEND_PORT"
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo ""
echo "Container is ready to accept connections"
echo ""

# Keep container running
wait $BACKEND_PID $FRONTEND_PID
