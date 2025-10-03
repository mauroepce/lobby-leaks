# =============================================================================
# Multi-stage Dockerfile for LobbyLeaks Service Template
# =============================================================================
# Stage 1: Builder - compiles dependencies and prepares wheels
# Stage 2: Runtime - minimal image with only runtime dependencies
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Set working directory
WORKDIR /build

# Install build dependencies for compiling Python packages
# - gcc, g++: Required for compiling C extensions (psycopg, cryptography, etc.)
# - libpq-dev: PostgreSQL development headers for psycopg binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker layer caching
# If requirements.txt doesn't change, this layer is cached
COPY requirements.txt .

# Install dependencies to a prefix we can copy
# - --no-cache-dir: Don't cache pip packages (saves space)
# - --prefix=/install: Install to /install for easy copying
RUN pip install --no-cache-dir --prefix=/install \
    -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Runtime
# -----------------------------------------------------------------------------
FROM python:3.12-slim

# Metadata labels (OCI standard)
LABEL org.opencontainers.image.title="LobbyLeaks Service Template"
LABEL org.opencontainers.image.description="Reusable template for LobbyLeaks data ingestion services"
LABEL org.opencontainers.image.vendor="LobbyLeaks"
LABEL org.opencontainers.image.source="https://github.com/mauroepce/lobby-leaks"

# Install only runtime dependencies (not build tools)
# - libpq5: PostgreSQL client library (needed for psycopg at runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
# - --system: Create a system user (no password, no home dir by default)
# - --group: Create a group with the same name
# - appuser: Conventional name for application user
RUN adduser --system --group --no-create-home appuser

# Set working directory
WORKDIR /app

# Copy installed packages from builder stage
# This brings only the compiled wheels, not the build tools
COPY --from=builder /install /usr/local

# Copy application code
# .dockerignore ensures we don't copy tests, .venv, __pycache__, etc.
COPY --chown=appuser:appuser . .

# Add /app to PYTHONPATH so imports work correctly
ENV PYTHONPATH=/app

# Switch to non-root user
USER appuser

# Health check (optional - verifies Python and imports work)
# Runs every 30s, times out after 3s, considers unhealthy after 3 failures
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD python -c "from settings import settings; import sys; sys.exit(0)" || exit 1

# Default entrypoint: run the service CLI
# Users can override CMD to pass different arguments
# Example: docker run <image> --since 2025-01-01 --log-level DEBUG
ENTRYPOINT ["python", "run.py"]

# Default command: show help if no args provided
CMD ["--help"]
