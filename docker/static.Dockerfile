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

# Build Django-side static file bundle
RUN uv run --no-sync manage.py collectstatic --no-input

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

FROM nginx:1.29.3-alpine3.22

RUN chown 101:101 -R /var/cache/nginx/ /var/log/nginx/
RUN touch /run/nginx.pid && chown 101:101 /run/nginx.pid
USER 101

COPY --from=build_frontend --chown=101 /app/dist /app/static
COPY --from=build_backend --chown=101 /app/static/backend /app/static/backend

COPY ./nginx.conf /etc/nginx/nginx.conf
