# OpenHands Container Image with WorktreeRuntime
# This image includes everything needed to run OpenHands in a Linux container

FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app/

# Install Python dependencies
RUN uv sync --locked

# Build frontend
RUN cd frontend && npm install && npm run build && cd ..

# Expose ports
EXPOSE 3000 3001

# Environment variables
ENV RUNTIME=worktree
ENV BACKEND_HOST=0.0.0.0
ENV BACKEND_PORT=3000
ENV FRONTEND_PORT=3001
ENV PYTHONUNBUFFERED=1

# Generate a default secret key (override with -e OH_SECRET_KEY=...)
ENV OH_SECRET_KEY=default_secret_change_in_production

# Start script
COPY podman-start.sh /app/podman-start.sh
RUN chmod +x /app/podman-start.sh

CMD ["/app/podman-start.sh"]
