# OpenHands Podman Setup Guide

Run OpenHands with WorktreeRuntime using Podman Linux containers. This provides full Linux compatibility including the V1 conversation API.

## Why Podman?

| Feature | Windows Native | Podman Container |
|---------|---------------|------------------|
| WorktreeRuntime | ✅ | ✅ |
| V1 Conversations | ❌ Broken | ✅ Works |
| fcntl support | ❌ No | ✅ Yes (Linux) |
| Rootless | N/A | ✅ Supported |
| Daemonless | N/A | ✅ Supported |

## Prerequisites

### Windows

1. **Install Podman Desktop**: https://podman-desktop.io/downloads
2. **Or install via CLI**:
   ```powershell
   winget install RedHat.Podman
   ```

3. **Initialize Podman machine** (first time only):
   ```powershell
   podman machine init
   podman machine start
   ```

### Linux

```bash
# Ubuntu/Debian
sudo apt-get install podman podman-compose

# Fedora
sudo dnf install podman podman-compose

# Arch
sudo pacman -S podman podman-compose
```

### macOS

```bash
brew install podman podman-compose
podman machine init
podman machine start
```

## Quick Start

### Option 1: Using the run script

```bash
# Build and run
bash run_podman.sh
```

This will:
1. Build the container image
2. Start the container
3. Wait for services
4. Show you the URLs

### Option 2: Using podman-compose

```bash
# Build and start
podman-compose up -d

# View logs
podman-compose logs -f

# Stop
podman-compose down
```

### Option 3: Manual podman commands

```bash
# Build image
podman build -t openhands-worktree:latest -f Containerfile .

# Run container
podman run -d \
    --name openhands-worktree \
    -p 3000:3000 \
    -p 3001:3001 \
    -e RUNTIME=worktree \
    -e OH_SECRET_KEY=$(openssl rand -hex 32) \
    -v "$(pwd)/workspace:/workspace" \
    openhands-worktree:latest
```

## Accessing OpenHands

Once running, access from your browser:

- **Frontend**: http://localhost:3001
- **Backend**: http://localhost:3000

## Container Management

### View logs
```bash
podman logs -f openhands-worktree
```

### Stop container
```bash
podman stop openhands-worktree
```

### Restart container
```bash
podman restart openhands-worktree
```

### Enter container shell
```bash
podman exec -it openhands-worktree bash
```

### Remove container
```bash
podman rm -f openhands-worktree
```

### Update image after code changes
```bash
podman build -t openhands-worktree:latest -f Containerfile .
podman restart openhands-worktree
```

## Configuration

### Environment Variables

Create a `.env` file:

```bash
OH_SECRET_KEY=your_random_64_char_hex_string
RUNTIME=worktree
BACKEND_HOST=0.0.0.0
BACKEND_PORT=3000
FRONTEND_PORT=3001
```

### Workspace Persistence

The `workspace/` directory is mounted into the container for persistence:

```bash
# Local workspace → Container /workspace
./workspace:/workspace
```

### Git Configuration

Your local git config is mounted for repository access:

```bash
~/.gitconfig:/root/.gitconfig:ro
```

## Troubleshooting

### Port already in use

```bash
# Find process using port 3000/3001
podman ps

# Stop conflicting container
podman stop <container_name>
```

### Container fails to start

```bash
# Check logs
podman logs openhands-worktree

# Run interactively to see errors
podman run -it --rm \
    -p 3000:3000 \
    -p 3001:3001 \
    openhands-worktree:latest
```

### Build fails

```bash
# Clean build
podman build --no-cache -t openhands-worktree:latest -f Containerfile .
```

### Podman machine issues (Windows/macOS)

```bash
# Check machine status
podman machine list

# Restart machine
podman machine stop
podman machine start

# Recreate machine
podman machine rm
podman machine init
podman machine start
```

## Comparison with Docker

| Feature | Docker | Podman |
|---------|--------|--------|
| Daemon | Required | Not required |
| Root privileges | Often needed | Rootless by default |
| Kubernetes | docker-compose | podman-compose |
| CLI compatibility | docker | podman (drop-in replacement) |
| License | Docker Desktop paid for enterprise | Open source |

## Advanced: Rootless Mode

Podman runs rootless by default on Linux:

```bash
# Check if rootless
podman info | grep rootless

# Rootless containers run as your user
# Ports < 1024 require configuration
```

To use ports < 1024 in rootless mode:

```bash
# Allow binding to port 80
sudo sysctl net.ipv4.ip_unprivileged_port_start=80
```

## Migration from Docker

If you have Docker installed, you can alias it:

```bash
alias docker=podman
```

Or use the Docker compatibility layer:

```bash
# Install podman-docker (Linux)
sudo apt-get install podman-docker
```

Then use `docker` commands as normal.
