# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .
COPY pyproject.toml .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY src/ ./src/
COPY README.md .

# Install the package
RUN pip install --no-cache-dir -e .

# Create directories for data and config
RUN mkdir -p /data /config

# Set environment variables for data and config paths
ENV DATABASE_PATH=/data/ytsum.db
ENV LOG_PATH=/data/logs

# Expose port for web interface
EXPOSE 5000

# Health check for web interface
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000').read()" || exit 1

# Default command runs the web interface
CMD ["ytsum", "web", "--host", "0.0.0.0", "--port", "5000"]
