# Base image: Lightweight Python 3.9 (Stable & Secure)
FROM python:3.9-slim

# Prevent Python from writing pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
# 'curl' is required for the healthcheck defined in docker-compose.yml
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Upgrade pip (Stability Best Practice)
RUN pip install --upgrade pip

# Install Python dependencies
# Copy requirements FIRST to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# SECURITY & PERMISSIONS:
# 1. Create non-root user 'sentinel'
# 2. Grant ownership of /app to 'sentinel' (CRITICAL for Streamlit/Python write access)
RUN useradd -m sentinel \
    && chown -R sentinel:sentinel /app

# Switch to non-root user
USER sentinel

# Expose ports (Documentation only)
EXPOSE 8000 8501

# Default entrypoint (API Server)
CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]