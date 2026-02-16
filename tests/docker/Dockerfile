# Test Dockerfile for nfo documentation validation
# This image tests all documented commands and examples

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml VERSION README.md LICENSE /app/
COPY nfo/ /app/nfo/

# Install nfo from local source
RUN pip install --no-cache-dir /app

# Install optional dependencies for full testing
RUN pip install --no-cache-dir fastapi uvicorn prometheus_client

# Copy examples
COPY examples/ /app/examples/

# Copy test suite
COPY tests/docker/test_docs.py /app/test_docs.py

# Set environment
ENV PYTHONPATH=/app
ENV NFO_LOG_DIR=/tmp/nfo_logs

# Run tests
CMD ["python", "/app/test_docs.py"]
