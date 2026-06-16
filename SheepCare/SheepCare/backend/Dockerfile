FROM python:3.13-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY backend/requirements.txt .

# Install PerfectSSL intermediate CA (needed for sheepcare.cnta.es HTTPS)
COPY backend/PerfectSSL.crt /usr/local/share/ca-certificates/PerfectSSL.crt
RUN update-ca-certificates
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire backend
COPY backend/ ./backend/
COPY run.py .

# Copy ML model
COPY models/ ./models/

# Ensure data directory exists
RUN mkdir -p /app/backend/data

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
