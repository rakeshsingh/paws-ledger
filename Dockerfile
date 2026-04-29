# Use a slim, stable Python base image
FROM python:3.11-slim-bookworm

# Install uv binary from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1

# Install dependencies
# We use a cache mount to speed up subsequent builds
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    uv pip install --system -r requirements.txt

# Copy the application code
COPY . .

# Create a non-root user for security
RUN useradd -m pawsuser && chown -R pawsuser:pawsuser /app
USER pawsuser

# Application configuration
ENV APP_ENV=prod
ENV PYTHONUNBUFFERED=1

# Expose the port NiceGUI/FastAPI runs on
EXPOSE 8080

# Command to run the application
CMD ["python", "-m", "app.main"]
