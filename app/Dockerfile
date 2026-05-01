FROM python:3.11-slim

WORKDIR /

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the rest of the application
COPY . /app

# Set environment variables
ENV APP_ENV=prod
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/

# Expose port
EXPOSE 8080

# Run using uvicorn directly for better production handling
CMD ["uvicorn", "app.main:fastapi_app", "--host", "0.0.0.0", "--port", "8080"]
