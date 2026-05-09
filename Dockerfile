# Multi-stage Dockerfile for LNN Manufacturing AI Service
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    APP_HOME=/app

WORKDIR $APP_HOME

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Build stage ----
FROM base AS build

COPY python/ $APP_HOME/python/
COPY .env.example $APP_HOME/.env.example

# ---- Production stage ----
FROM base AS production

ENV APP_ENV=production \
    PORT=8000

COPY --from=build $APP_HOME $APP_HOME

RUN groupadd -r appuser && useradd -r -g appuser -d $APP_HOME -s /sbin/nologin appuser \
    && chown -R appuser:appuser $APP_HOME

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

ENV PYTHONPATH=/app/python

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
