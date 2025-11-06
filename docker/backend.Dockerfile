FROM python:3.12.11-alpine3.22 AS build_backend
COPY --from=ghcr.io/astral-sh/uv:0.8.18 /uv /uvx /bin/

WORKDIR /app

# Install dependencies
COPY uv.lock .
COPY pyproject.toml .
RUN uv sync --no-dev --frozen --compile-bytecode --no-install-project

COPY src/firetower .

# Install the backend itself
COPY pyproject.toml .
COPY manage.py .
COPY README.md .
COPY src/ src/
RUN uv sync --group prod --no-dev --frozen --compile-bytecode --no-editable

FROM python:3.12.11-alpine3.22

RUN adduser app -h /app -u 1100 -D && chown -R 1100 /app

# Copy the environment, but not the source code
COPY --from=build_backend --chown=1100 /app/.venv /app/.venv

WORKDIR /app
USER 1100

ENV PORT=8080
EXPOSE $PORT

ENV DJANGO_ENV="prod"
ENTRYPOINT [ "sh", "-c", "/app/.venv/bin/granian --interface wsgi --host 0.0.0.0 --port $PORT firetower.wsgi:application"]
