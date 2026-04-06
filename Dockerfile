# Production Backend Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy backend code
COPY backend/ ./backend/
COPY trading/ ./trading/
COPY scripts/ ./scripts/

# Create necessary directories
RUN mkdir -p /app/logs /app/config /app/data

# Set permissions
RUN chmod +x /app/scripts/*.py 2>/dev/null || true

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with gunicorn for production
CMD ["gunicorn", "backend.app:app", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2", "--worker-class", "sync", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "--enable-stdio-inheritance"]
