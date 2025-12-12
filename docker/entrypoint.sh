#!/bin/sh

set -e
set -u
set -x

if [ z"$1" = "zmigrate" ]; then
    COMMAND="/app/.venv/bin/django-admin migrate --settings firetower.settings"
elif [ z"$1" = "zserver" ]; then
    COMMAND="/app/.venv/bin/granian --interface wsgi --host 0.0.0.0 --port $PORT firetower.wsgi:application"
else
    echo "Usage: $0 (migrate|server)"
    exit 1
fi

export PYTHONPATH=/app:\$PYTHONPATH
/app/.venv/bin/ddtrace-run $COMMAND
