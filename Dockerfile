# Use slim Python 3.11 base image
FROM python:3.11-slim

# Prevent Python from writing .pyc files & buffer stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production

# Install FFmpeg (required for video dubbing & audio processing) and curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency definition files
COPY pyproject.toml uv.lock ./

# Install third-party dependencies only (skip building the local project,
# since app/ hasn't been copied in yet). This layer stays cached as long
# as pyproject.toml/uv.lock don't change.
RUN uv sync --frozen --no-cache --no-install-project

# Copy application source code
COPY . .

# Now install the project itself (app/__init__.py exists now)
RUN uv sync --frozen --no-cache

# Create media folders required at runtime
RUN mkdir -p static/uploads static/processed outputs

# Render dynamically sets the PORT environment variable (default fallback 5000)
EXPOSE 5000

# Start server directly with uvicorn, respecting Render's dynamic PORT.
# Shell form (no brackets) is required so ${PORT:-5000} actually gets expanded.
CMD uv run uvicorn app:app --host 0.0.0.0 --port ${PORT:-5000}