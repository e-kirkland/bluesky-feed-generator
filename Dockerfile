FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create data directory for SQLite and set permissions
RUN mkdir -p /app/data && \
    chown -R 1000:1000 /app/data && \
    chmod 777 /app/data

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create a non-root user and switch to it
RUN useradd -m ubuntu && chown -R ubuntu:ubuntu /app
USER ubuntu

# Change permissions for data directory
RUN chown -R ubuntu:ubuntu /app/data && \
    chmod 777 /app/data

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose the port the app runs on
EXPOSE 8080

# Command to run the application is now in docker-compose.yml 