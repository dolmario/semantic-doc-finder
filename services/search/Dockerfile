FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy and install requirements
COPY services/search/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY services/search/api.py api.py
COPY services/anonymizer.py anonymizer.py

# Create necessary directories
RUN mkdir -p /app/logs

CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
