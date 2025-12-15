from logging import warning
from typing import TypedDict, Unpack

from datadog.api.events import Event
from datadog.api.exceptions import DatadogException
from django.db.models.signals import post_migrate, pre_migrate
from django.dispatch import receiver

from firetower.settings import env_is_dev


class MigrationSignalArgs(TypedDict):
    plan: tuple[str, bool]


def log_datadog_event(
    title: str, text: str = "", alert_type: str = "info", tags: list[str] = []
) -> None:
    if not env_is_dev():
        try:
            tags += ["source:firetower"]
            result = Event.create(
                True,
                text=text,
                tags=tags,
                alert_type=alert_type,
            )
            print(repr(result))
        except (ImportError, DatadogException) as e:
            warning(f"Failed to log datadog event: {e}")


@receiver(pre_migrate)
def log_pre_migrate(**kwargs: Unpack[MigrationSignalArgs]) -> None:
    plan = kwargs.get("plan")
    log_datadog_event(
        title="Firetower: Django migration started", text=f"Plan:\n\n{repr(plan)}"
    )


@receiver(post_migrate)
def log_post_migrate(**kwargs: Unpack[MigrationSignalArgs]) -> None:
    plan = kwargs.get("plan")
    log_datadog_event(
        title="Firetower: Django migration finished", text=f"Plan:\n\n{repr(plan)}"
    )
