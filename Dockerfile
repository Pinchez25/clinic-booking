# --- Stage 1: Build dependencies ---
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install production dependencies into a virtual environment
RUN uv sync --no-dev --frozen

# --- Stage 2: Production image ---
FROM python:3.12-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Create non-root user
RUN addgroup --system clinic && adduser --system --ingroup clinic clinic

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Collect static files
RUN python manage.py collectstatic --no-input --settings=clinic.settings.production \
    || true  # collectstatic can fail without DB _ acceptable at build time

# Drop to non-root user
USER clinic

EXPOSE 8000

CMD ["gunicorn", "clinic.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60"]
