FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Chromium for Playwright
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m playwright install chromium 2>/dev/null; exit 0

# Copy application code
COPY backend/app/ ./app/
COPY migrations/ ./migrations/
COPY backend/pyproject.toml .

# Create entrypoint script (no alembic - tables already exist in the host database)
# When the container command passes arguments (celery worker / beat in
# docker-compose), execute them directly instead of the uvicorn API server.
RUN printf '#!/bin/bash\ncd /app\nif [ "$#" -gt 0 ]; then\n  echo "Starting: $*"\n  exec "$@"\nfi\necho "Starting Gadgeto backend..."\nuvicorn app.main:app --host 0.0.0.0 --port 8000\n' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
EXPOSE 8000
