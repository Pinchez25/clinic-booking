FROM python:3.14.0-slim AS builder
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --compile-bytecode

FROM python:3.14.0-slim AS production
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Uncomment and adjust if your DB driver needs native libs (e.g. libpq5 for psycopg)
# RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
#     && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN addgroup --system clinic && adduser --system --ingroup clinic clinic

COPY --from=builder /app/.venv /app/.venv
COPY --chown=clinic:clinic . .
RUN mkdir -p /app/staticfiles && chown clinic:clinic /app/staticfiles
USER clinic

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/', timeout=5)" || exit 1

EXPOSE 8000
STOPSIGNAL SIGTERM
CMD ["gunicorn", "clinic.wsgi:application", "--config", "gunicorn.conf.py"]
