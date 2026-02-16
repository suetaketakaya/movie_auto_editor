#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head || echo "WARNING: Migration failed or no migrations to run"

echo "Starting application..."
WORKERS=${UVICORN_WORKERS:-2}
exec uvicorn backend.src.adapters.inbound.fastapi_app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers "$WORKERS" \
  --access-log \
  --proxy-headers \
  --forwarded-allow-ips="*"
