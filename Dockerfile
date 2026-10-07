# syntax=docker/dockerfile:1

# ---- build: install the locked dependencies into a virtualenv ----
FROM python:3.13-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ---- runtime: the app, its virtualenv, and nothing else ----
FROM python:3.13-slim

# DJANGO_ENV=production turns on strict mode in config/settings.py.
ENV DJANGO_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8080

WORKDIR /app
RUN useradd --system --uid 10001 --no-create-home app

COPY --from=build /app/.venv /app/.venv
COPY manage.py ./
COPY config ./config
COPY content ./content
COPY portfolio ./portfolio

# Hash and compress static files into the image. The key here only lets
# settings load during the build; the real one comes from the environment.
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput

USER app
EXPOSE 8080

# One worker with threads suits a small Cloud Run instance; Cloud Run handles
# request timeouts itself, hence --timeout 0.
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT} --workers 1 --threads 8 --timeout 0 --access-logfile -"]
