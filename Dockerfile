# Use Python 3.10.16
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

# Default command (can be overridden in docker-compose.yml)
# CMD ["python", "app.py"]
CMD ["gunicorn", "app:app","--bind", "0.0.0.0:5001", "--workers", "3", "--reload"]