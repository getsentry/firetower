FROM python:3.12.11-alpine3.22 AS build_mcp
COPY --from=ghcr.io/astral-sh/uv:0.8.18 /uv /uvx /bin/

WORKDIR /app

COPY uv.lock .
COPY pyproject.toml .
COPY README.md .
COPY src/ src/
COPY sdk/ sdk/
RUN uv sync --group mcp --no-dev --frozen --compile-bytecode --no-editable

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

COPY --from=datadog/serverless-init:1.8.2-alpine /datadog-init /app/datadog-init

COPY --from=build_mcp --chown=1100 /app/.venv /app/.venv
COPY docker/entrypoint.sh /app/entrypoint.sh

WORKDIR /app
USER 1100

ENV PORT=8080
EXPOSE $PORT

ENTRYPOINT [ "/app/datadog-init" ]
CMD [ "/app/entrypoint.sh", "mcp" ]
