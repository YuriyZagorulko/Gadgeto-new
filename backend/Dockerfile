FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY pyproject.toml .

# Create entrypoint script
RUN echo '#!/bin/bash\n\
cd /app\n\
echo "Running database migrations..."\n\
alembic upgrade head\n\
echo "Starting application..."\n\
uvicorn app.main:app --host 0.0.0.0 --port 8000\n\
' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
EXPOSE 8000
