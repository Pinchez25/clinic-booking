FROM python:3.14-slim AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

RUN uv sync --no-dev --frozen

FROM python:3.14-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN addgroup --system clinic && adduser --system --ingroup clinic clinic

COPY --from=builder /app/.venv /app/.venv

COPY . .

USER clinic

EXPOSE 8000

CMD ["gunicorn", "clinic.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60"]
