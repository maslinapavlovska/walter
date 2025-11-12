# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (chromium only for smaller image)
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

# Create directory for logs
RUN mkdir -p /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "bot.py"]
