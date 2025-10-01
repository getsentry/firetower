FROM python:3.12-alpine3.22 AS python_base

FROM python_base AS build_backend
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
RUN ls -la
RUN uv sync --group prod --no-dev --frozen --compile-bytecode --no-editable

FROM oven/bun:1.2.22-alpine AS build_frontend

WORKDIR /app
COPY frontend/bun.lock .
COPY frontend/package.json .
RUN bun install --frozen-lockfile

COPY frontend/package.json .
COPY frontend/tsconfig*.json ./
COPY frontend/vite.config.ts .
COPY frontend/index.html .
COPY frontend/env.ts .
COPY frontend/src ./src/

RUN bun run build

FROM python_base

# Copy the environment, but not the source code
COPY --from=build_backend --chown=app:app /app/.venv /app/.venv
COPY --from=build_frontend --chown=app:app /app/dist /app/static

USER app
WORKDIR /app

ENTRYPOINT [ "/app/.venv/bin/granian", "--interface", "wsgi", "firetower.wsgi:application"]
