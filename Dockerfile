# =============================================================================
# Multi-stage Dockerfile for LNN Manufacturing AI Service
# Optimized for minimal image size (< 1.5GB) and build efficiency
# =============================================================================

# ---- Stage 1: Dependencies Build ----
FROM python:3.11-slim AS dependencies

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /install

# Install only build dependencies needed for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements file for better layer caching
COPY requirements.txt .

# Install Python dependencies to a virtual environment
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: Production Runtime ----
FROM python:3.11-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    APP_HOME=/app \
    PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV="/opt/venv" \
    APP_ENV=production \
    PORT=8000 \
    PYTHONPATH=/app/python

WORKDIR $APP_HOME

# Install only runtime dependencies (no compilers needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# Copy virtual environment from dependencies stage
COPY --from=dependencies /opt/venv /opt/venv

# Copy application code (excluding .git, logs, tests, etc. via .dockerignore)
COPY python/ $APP_HOME/python/

# Create non-root user and set permissions
RUN groupadd -r appuser && useradd -r -g appuser -d $APP_HOME -s /sbin/nologin appuser && \
    chown -R appuser:appuser $APP_HOME

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
