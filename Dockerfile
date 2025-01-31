FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create data directory for SQLite and set permissions
RUN mkdir -p /app/data && \
    chmod 777 /app/data

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create ubuntu user with specific UID/GID
RUN groupadd -g 1001 ubuntu && \
    useradd -u 1001 -g ubuntu -m ubuntu && \
    chown -R ubuntu:ubuntu /app && \
    chown -R ubuntu:ubuntu /app/data

# Ensure the database file exists and has proper permissions
RUN touch /app/data/feed.db && \
    chown ubuntu:ubuntu /app/data/feed.db && \
    chmod 666 /app/data/feed.db

USER ubuntu:ubuntu

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Expose the port the app runs on
EXPOSE 5000

# Command to run the application is now in docker-compose.yml 