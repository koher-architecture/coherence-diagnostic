# Coherence Diagnostic - Koher Tool
# MIT License - https://koher.app

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
COPY config.py .
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY src/ ./src/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Copy config.env.example as reference (user should create config.env)
COPY config.env.example .

# Environment variables (Python)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# =============================================================================
# Feature Toggle
# =============================================================================

# Enable gated access (email verification + admin panel)
# Set to 0 for open access (anyone can use the tool)
# Set to 1 for gated access (users must verify email, admin panel at /admin)
ENV ENABLE_AUTH=0

# =============================================================================
# Required: OpenRouter API (always required)
# =============================================================================
ENV OPENROUTER_API_KEY=""

# =============================================================================
# Auth Configuration (only needed if ENABLE_AUTH=1)
# =============================================================================

# Session secret for cookie signing
ENV SESSION_SECRET=""

# Admin password for /admin panel
ENV ADMIN_PASSWORD=""

# Base URL for verification emails
ENV BASE_URL="http://localhost:8000"

# Usage limits
ENV MAX_ANALYSES_PER_USER=10
ENV MAX_NEW_USERS_PER_DAY=10

# =============================================================================
# SMTP Configuration (optional, only used if ENABLE_AUTH=1)
# =============================================================================
# If not configured, verification links are printed to console.
# Works with any SMTP provider (SendGrid, Mailgun, AWS SES, Postmark, etc.)
ENV SMTP_HOST=""
ENV SMTP_PORT="587"
ENV SMTP_USERNAME=""
ENV SMTP_PASSWORD=""
ENV SMTP_FROM_EMAIL="noreply@example.com"
ENV SMTP_FROM_NAME="Coherence Diagnostic"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Entrypoint downloads model on first run, then starts uvicorn
ENTRYPOINT ["./entrypoint.sh"]
