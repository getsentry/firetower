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

ENV \
      PYTHONUNBUFFERED="True" \
      DD_FLUSH_TO_LOG="true" \
      DD_TRACE_ENABLED="false" \
      DD_APM_ENABLED="false" \
      DD_LOGS_ENABLED="false" \
      DD_LOGS_INJECTION="false" \
      DD_SOURCE="python"

RUN adduser app -h /app -u 1100 -D && chown -R 1100 /app

# DD agent setup
COPY --from=datadog/serverless-init:1.8.2-alpine /datadog-init /app/datadog-init

# Copy the environment, but not the source code
COPY --from=build_backend --chown=1100 /app/.venv /app/.venv
COPY docker/entrypoint.sh /app/entrypoint.sh

WORKDIR /app
USER 1100

ENV PORT=8080
EXPOSE $PORT

ENV DJANGO_ENV="prod"
ENV GRANIAN_RUNTIME_THREADS="2"
ENV GRANIAN_BACKPRESSURE="32"

ENTRYPOINT [ "/app/datadog-init" ]
CMD [ "entrypoint.sh", "server" ]
