# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY backend/requirements.txt ./backend/

# Install Python dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Copy frontend code
COPY frontend/ ./frontend/

# Create data directories
RUN mkdir -p data/bean_files data/chroma_db

# Expose port
EXPOSE 8000

# Set working directory to backend
WORKDIR /app/backend

# Run the application
CMD ["python", "main.py"]
