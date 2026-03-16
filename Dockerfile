FROM python:3.13-slim

# Install system dependencies for scrapling (playwright/camoufox browsers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies only (no project itself yet)
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code and files needed for build
COPY README.md ./
COPY src/ src/
COPY docker/ docker/

# Install the project (creates hkjc-scrape entry point)
RUN uv sync --frozen --no-dev

# Create data directory
RUN mkdir -p /app/data

# Default entrypoint
ENTRYPOINT ["uv", "run", "hkjc-scrape"]
