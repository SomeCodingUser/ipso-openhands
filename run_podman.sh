#!/bin/bash
# Run OpenHands with Podman (Linux containers)

set -e

echo "=========================================="
echo "OpenHands with Podman"
echo "=========================================="
echo ""

# Check if podman is installed
if ! command -v podman &> /dev/null; then
    echo "ERROR: Podman is not installed!"
    echo ""
    echo "Install Podman:"
    echo "  Windows: https://github.com/containers/podman/releases"
    echo "  Linux: sudo apt-get install podman"
    echo "  macOS: brew install podman"
    exit 1
fi

echo "Podman version: $(podman --version)"
echo ""

# Generate secret key
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

if [ -z "$OH_SECRET_KEY" ]; then
    export OH_SECRET_KEY=$(openssl rand -hex 32)
    echo "OH_SECRET_KEY=$OH_SECRET_KEY" > .env
    echo "Generated OH_SECRET_KEY and saved to .env"
fi

# Container name
CONTAINER_NAME="openhands-worktree"
IMAGE_NAME="openhands-worktree:latest"

# Check if container is already running
if podman ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container $CONTAINER_NAME is already running!"
    echo ""
    echo "To stop: podman stop $CONTAINER_NAME"
    echo "To restart: podman restart $CONTAINER_NAME"
    exit 0
fi

# Check if image exists, build if not
if ! podman image exists $IMAGE_NAME; then
    echo "Building container image..."
    podman build -t $IMAGE_NAME -f Containerfile .
    echo "Build complete!"
    echo ""
fi

# Create workspace directory
mkdir -p workspace

# Run container
echo "Starting OpenHands container..."
podman run -d \
    --name $CONTAINER_NAME \
    --replace \
    -p 3000:3000 \
    -p 3001:3001 \
    -e RUNTIME=worktree \
    -e BACKEND_HOST=0.0.0.0 \
    -e BACKEND_PORT=3000 \
    -e FRONTEND_PORT=3001 \
    -e OH_SECRET_KEY=$OH_SECRET_KEY \
    -e PYTHONUNBUFFERED=1 \
    -v "$(pwd)/workspace:/workspace" \
    -v "$HOME/.gitconfig:/root/.gitconfig:ro" \
    $IMAGE_NAME

echo ""
echo "Container started!"
echo ""

# Wait for services
echo "Waiting for services to be ready..."
for i in {1..60}; do
    if curl -s http://localhost:3001 > /dev/null 2>&1; then
        echo ""
        echo "=========================================="
        echo "OpenHands is ready!"
        echo "=========================================="
        echo ""
        echo "Frontend: http://localhost:3001"
        echo "Backend:  http://localhost:3000"
        echo ""
        echo "Container: $CONTAINER_NAME"
        echo ""
        echo "View logs: podman logs -f $CONTAINER_NAME"
        echo "Stop:      podman stop $CONTAINER_NAME"
        echo "Shell:     podman exec -it $CONTAINER_NAME bash"
        echo ""
        exit 0
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "WARNING: Services may not be fully ready yet."
echo "Check logs with: podman logs -f $CONTAINER_NAME"
