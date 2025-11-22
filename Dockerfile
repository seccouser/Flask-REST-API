FROM python:3.11-slim

# Install system dependencies for evdev
RUN apt-get update && apt-get install -y \
    gcc \
    linux-headers-generic || true \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY keyboard_emulator.py .

# Create uploads directory
RUN mkdir -p /app/uploads

# Expose port
EXPOSE 5000

# Set environment variables
ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=5000
ENV FLASK_DEBUG=False

# Run the application
CMD ["python", "app.py"]
