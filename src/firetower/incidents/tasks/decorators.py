import functools
import logging
import re
from typing import Any, Protocol

from datadog import statsd

DATADOG_INVALID_CHARS = re.compile(r"[^A-Za-z0-9-_.\/]")

logger = logging.getLogger(__name__)


class NamedFunction(Protocol):
    __name__: str

    def __call__(self, *args: Any, **kwargs: Any) -> None: ...


def datadog_log(f: NamedFunction) -> NamedFunction:
    task_name: str = DATADOG_INVALID_CHARS.sub("_", f.__name__)
    tags = [f"task:{task_name}"]

    @functools.wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        statsd.increment("django_q.task.run", 1, tags)
        try:
            f(*args, **kwargs)
        except Exception as e:
            statsd.increment("django_q.task.error", 1, tags)
            logger.error(
                f"Error while executing task '{task_name}': {e}", exc_info=True
            )
            raise e
        else:
            statsd.increment("django_q.task.success", 1, tags)

    return wrapper
