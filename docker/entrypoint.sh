#!/bin/sh

set -e
set -u
set -x

export PYTHONPATH="/app:${PYTHONPATH-}"

if [ z"$1" = "zmigrate" ]; then
    exec /app/.venv/bin/ddtrace-run /app/.venv/bin/django-admin migrate --settings firetower.settings
elif [ z"$1" = "zserver" ]; then
    exec /app/.venv/bin/ddtrace-run /app/.venv/bin/granian --interface wsgi --host 0.0.0.0 --port "${PORT}" firetower.wsgi:application
elif [ z"$1" = "zslack-bot" ]; then
    exec /app/.venv/bin/ddtrace-run /app/.venv/bin/django-admin run_slack_bot --settings firetower.settings
elif [ z"$1" = "zworker" ]; then
    exec /app/.venv/bin/ddtrace-run /app/.venv/bin/django-admin qcluster --settings firetower.settings
else
    echo "Usage: $0 (migrate|server|slack-bot|worker)"
    exit 1
fi
