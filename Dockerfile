# syntax=docker/dockerfile:1

# =============================================================
# Stage 1: Build the React Frontend SPA
# =============================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# =============================================================
# Stage 2: Python Backend + Integrated Single-Site Serving
# =============================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    PORT=8000

WORKDIR /app

# Install system dependencies (curl for health checks)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY backend/requirements.txt /app/backend/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# Create application user and persistent folders
RUN useradd -u 1000 -m -s /bin/bash appuser && \
    mkdir -p /app/backend/output /app/data && \
    chown -R appuser:appuser /app

# Copy Backend Source Code
COPY --chown=appuser:appuser backend/ /app/backend/

# Copy Compiled Frontend Production Bundle from Stage 1
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/dist /app/frontend/dist

# Switch to non-root user
USER appuser

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT:-8000}/api/health || exit 1

# Start Uvicorn dynamically binding to Render's $PORT
CMD ["sh", "-c", "python -m uvicorn app.main:app --app-dir /app/backend --host 0.0.0.0 --port ${PORT:-8000}"]
