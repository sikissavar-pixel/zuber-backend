# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app

# Copy database initialization script
COPY init_db.py .

# Create static directory if it doesn't exist
RUN mkdir -p app/static

# Create non-root user
RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port (Railway will override this with $PORT)
EXPOSE 8000

# Start uvicorn server with shell to expand $PORT
# Run database initialization before starting server
CMD sh -c "python init_db.py && uvicorn app.main:socket_app --host 0.0.0.0 --port ${PORT}"
