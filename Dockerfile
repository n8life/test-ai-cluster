FROM python:3.11-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (layer cache)
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

# Copy application code
COPY app/ ./app/

# Run the test script via uv
CMD ["uv", "run", "python", "-m", "app.main"]
