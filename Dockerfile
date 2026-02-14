# Coherence Diagnostic - Koher Tool
# Multi-stage build for smaller image

FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Model download stage
FROM python:3.11-slim as model-downloader

WORKDIR /app

# Install git and git-lfs for model download
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    git-lfs \
    && rm -rf /var/lib/apt/lists/* \
    && git lfs install

# Clone only the models directory using sparse checkout
RUN git clone --filter=blob:none --no-checkout --depth 1 \
    https://github.com/koher-architecture/coherence-diagnostic.git . \
    && git sparse-checkout init --cone \
    && git sparse-checkout set models \
    && git checkout main

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy model from downloader stage
COPY --from=model-downloader /app/models ./models/

# Copy application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY src/ ./src/

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Admin password (must be set in deployment)
ENV ADMIN_PASSWORD=""

# Anthropic API key (must be set in deployment)
ENV ANTHROPIC_API_KEY=""

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
