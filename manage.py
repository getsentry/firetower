#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
from logging import warning

from datadog.api.events import Event
from datadog.api.exceptions import DatadogException


def log_datadog_event(
    title: str, text: str = "", alert_type: str = "info", tags: list[str] = []
) -> None:
    try:
        # We may not be able to load settings.py yet -- some commands don't
        # require it, but it should be set properly in prod.
        from firetower.settings import env_is_dev

        if not env_is_dev():
            tags += ["source:firetower"]
            Event.create(
                True,
                text=str(repr(sys.argv)),
                tags=tags,
                alert_type=alert_type,
            )
    except (ImportError, DatadogException) as e:
        warning(f"Failed to log datadog event: {e}")


def django_main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "firetower.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


def main():
    log_datadog_event(
        title="Firetower: Start Run Django Command",
        text=str(repr(sys.argv)),
    )

    exc = None
    try:
        django_main()
    except (Exception, SystemExit) as e:
        exc = e

    title = "Firetower: Finish Run Django Command"
    text = str(repr(sys.argv))
    exit_code = 0
    if exc is not None:
        if isinstance(exc, SystemExit):
            exit_code = exc.code
            text += f"\n\nExit code: {exit_code}"
        else:
            text += f"\n\nException: {exc.__class__}: {exc}"
    log_datadog_event(
        title=title,
        text=text,
    )
    if exc is not None:
        raise exc


if __name__ == "__main__":
    main()
