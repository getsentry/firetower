import functools
import logging
import re
from typing import Protocol

from datadog import statsd
from django_q.tasks import Schedule

from firetower.incidents.models import Incident

SCHEDULES = {
    "schedule_demo": {
        "func": "firetower.incidents.tasks.schedule_demo",
        "schedule_type": Schedule.MINUTES,  # Minutes
        "minutes": 5,
        "repeats": -1,  # repeat indefinitely
    },
}

DATADOG_INVALID_CHARS = re.compile(r"[^A-Za-z0-9-_.\/]")


logger = logging.getLogger(__name__)


class NamedFunction(Protocol):
    __name__: str

    def __call__(self) -> None:
        pass


def datadog_log(f: NamedFunction) -> NamedFunction:
    task_name: str = DATADOG_INVALID_CHARS.sub("_", f.__name__)
    tags = [f"task:{task_name}"]

    @functools.wraps(f)
    def wrapper() -> None:
        statsd.increment("django_q.task.run", 1, tags)
        try:
            f()
        except Exception as e:
            statsd.increment("django_q.task.error", 1, tags)
            logger.error(
                f"Error while executing task '{task_name}': {e}", exc_info=True
            )
            raise e
        else:
            statsd.increment("django_q.task.success", 1, tags)
        finally:
            # TODO(taylor-osler-sentry): Figure out if/why this is necessary?
            try:
                statsd.flush()
            except Exception as e:
                logger.error(
                    f"Error while flushing datadog metrics: {e}", exc_info=True
                )
                # Don't re-raise; it's more important we raise the inner exception, if present

    return wrapper


@datadog_log
def schedule_demo() -> None:
    incident = Incident.objects.order_by("-created_at").first()
    if incident:
        title = "Private Incident" if incident.is_private else incident.title
        logger.info(f"Most recent incident: INC-{incident.id}: {title}")
    else:
        logger.info("No incidents found.")
