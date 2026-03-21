FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install honcho for process management
RUN pip install --no-cache-dir honcho

# Expose port (Koyeb will set $PORT)
EXPOSE 8000

# Use honcho to run web + worker from Procfile
CMD ["honcho", "start"]
