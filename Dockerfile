# Coherence Diagnostic - Koher Tool

FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies (CPU-only PyTorch)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --user --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Install git and git-lfs for model download on first run
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    git-lfs \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY src/ ./src/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Admin password (must be set in deployment)
ENV ADMIN_PASSWORD=""

# OpenRouter API key (must be set in deployment)
ENV OPENROUTER_API_KEY=""

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Entrypoint downloads model on first run, then starts uvicorn
ENTRYPOINT ["./entrypoint.sh"]
