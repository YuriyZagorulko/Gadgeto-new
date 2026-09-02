#!/bin/bash
cd /app

# Celery services (docker-compose `command:`) pass their command here —
# execute it directly so worker/beat containers don't start uvicorn.
if [ "$#" -gt 0 ]; then
    echo "Starting: $*"
    exec "$@"
fi

echo "Starting Gadgeto backend..."
if [ "$ENVIRONMENT" = "development" ]; then
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
else
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi