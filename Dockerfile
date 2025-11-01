# Multi-stage Dockerfile für KR-Lead-Scraper
# Stage 1: Builder
FROM python:3.11-slim as builder

# Build Arguments
ARG DEBIAN_FRONTEND=noninteractive

# System Dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python Dependencies
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# Stage 2: Runtime
FROM python:3.11-slim

# Build Arguments
ARG DEBIAN_FRONTEND=noninteractive

# Labels
LABEL maintainer="Kunze & Ritter GmbH"
LABEL description="KR Lead Scraper - Automated B2B Lead Generation"

# System Dependencies (Runtime)
RUN apt-get update && apt-get install -y \
    # Playwright Dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    # Additional Tools
    curl \
    ca-certificates \
    libpq5 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create app user (security)
RUN useradd -m -u 1000 scraper && \
    mkdir -p /app /app/data /app/logs && \
    chown -R scraper:scraper /app

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/scraper/.local

# Copy application code
COPY --chown=scraper:scraper . .

# Switch to app user
USER scraper

# Add local bin to PATH
ENV PATH=/home/scraper/.local/bin:$PATH
ENV PYTHONPATH=/app

# Install Playwright browsers (as scraper user)
# Skip during build if PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD is set
# Can be installed at runtime or in environments with internet access
RUN python -m playwright install chromium || echo "Playwright browser installation skipped"

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
