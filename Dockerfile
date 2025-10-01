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
COPY frontend/public ./public/
COPY frontend/src ./src/

ENV VITE_API_URL="/api"

RUN bun run build

FROM python:3.12.11-alpine3.22

RUN adduser app -h /app -u 1100 -D && chown -R 1100 /app

# Copy the environment, but not the source code
COPY --from=build_backend --chown=1100 /app/.venv /app/.venv
COPY --from=build_frontend --chown=1100 /app/dist /app/static

WORKDIR /app
USER 1100

ENV PORT=8080
EXPOSE $PORT

ENV GRANIAN_STATIC_PATH_MOUNT="static/"
ENTRYPOINT [ "sh", "-c", "/app/.venv/bin/granian --interface wsgi --host 0.0.0.0 --port $PORT firetower.wsgi:application"]
