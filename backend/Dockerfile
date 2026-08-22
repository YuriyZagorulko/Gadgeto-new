FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/app/ ./app/
COPY migrations/ ./migrations/
COPY backend/pyproject.toml .

# Create entrypoint script (no alembic - tables already exist in the host database)
RUN echo '#!/bin/bash\n\
cd /app\n\
echo "Starting Gadgeto backend..."\n\
uvicorn app.main:app --host 0.0.0.0 --port 8000\n\
' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
EXPOSE 8000
