# Use Python 3.10.16 slim version
FROM python:3.10.16-slim

# Set the working directory
WORKDIR /app

# Install system dependencies required for gssapi
RUN apt-get update && apt-get install -y \
    build-essential \
    libkrb5-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port 5000 (for Flask)
EXPOSE 5000

# Default command (this can be overridden in docker-compose.yml)
CMD ["python", "app.py"]
