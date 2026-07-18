# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=webapp.py

# Install system dependencies (needed for psycopg2 and python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Copy the current directory contents into the container at /app
COPY . .

# Create directory for uploads and retained files
RUN mkdir -p uploads/retained

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Expose port 5000
EXPOSE 5000

# Use entrypoint to run migrations then start server
ENTRYPOINT ["/app/entrypoint.sh"]
