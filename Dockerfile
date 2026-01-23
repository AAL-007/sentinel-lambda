# Multi-stage build for production
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY src/ ./src/
COPY data/ ./data/

# Create non-root user
RUN useradd -m -u 1000 sentinel && chown -R sentinel: /app
USER sentinel

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(1); s.connect(('localhost', 8000)); s.close()" || exit 1

# Expose ports
EXPOSE 8000 8501

# Default command (can be overridden)
CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]