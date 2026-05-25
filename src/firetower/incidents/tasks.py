import functools
import logging
import re
import time
from typing import Protocol

from datadog import statsd
from django_q.tasks import Schedule

from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentStatus,
)
from firetower.integrations.services.slack import SlackService

SCHEDULES = {
    "schedule_demo": {
        "func": "firetower.incidents.tasks.schedule_demo",
        "schedule_type": Schedule.MINUTES,
        "minutes": 5,
        "repeats": -1,
    },
    "archive_stale_channels": {
        "func": "firetower.incidents.tasks.archive_stale_channels",
        "schedule_type": Schedule.DAILY,
        "repeats": -1,
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


ARCHIVE_NOTICE = (
    "This channel is being archived by Firetower because all message history "
    "has been removed by the workspace retention policy and there doesn't "
    "appear to be any active discussions."
)

ARCHIVE_CHANNEL_DELAY_SECONDS = 2


@datadog_log
def archive_stale_channels() -> None:
    slack = SlackService()
    if not slack.client:
        logger.error(
            "Slack client not initialized -- disabling archive_stale_channels schedule"
        )
        Schedule.objects.filter(name="archive_stale_channels").update(repeats=0)
        return

    own_bot_id = slack.bot_id
    if not own_bot_id:
        logger.error("Could not determine own bot ID, aborting archive run")
        return

    terminal_statuses = [IncidentStatus.DONE, IncidentStatus.CANCELLED]
    links = ExternalLink.objects.filter(
        type=ExternalLinkType.SLACK,
        incident__status__in=terminal_statuses,
    ).select_related("incident")

    scanned = 0
    archived = 0
    skipped = 0
    errored = 0

    for i, link in enumerate(links):
        if i > 0:
            time.sleep(ARCHIVE_CHANNEL_DELAY_SECONDS)

        scanned += 1
        channel_id = slack.parse_channel_id_from_url(link.url)
        if not channel_id:
            skipped += 1
            continue

        try:
            info = slack.get_channel_info(channel_id)
            if info is None:
                logger.warning(
                    f"Could not fetch info for channel {channel_id} "
                    f"(incident {link.incident.incident_number}), skipping"
                )
                skipped += 1
                continue

            if info.get("is_archived"):
                skipped += 1
                continue

            messages = slack.get_channel_history(channel_id)
            non_own_messages = [
                msg for msg in messages if msg.get("bot_id") != own_bot_id
            ]
            if non_own_messages:
                skipped += 1
                continue

            has_thread_activity = False
            for msg in messages:
                if msg.get("reply_count", 0) > 0:
                    replies = slack.get_thread_replies(channel_id, msg["ts"])
                    if replies:
                        has_thread_activity = True
                        break
            if has_thread_activity:
                skipped += 1
                continue

            notice_ts = slack.post_message(channel_id, ARCHIVE_NOTICE)
            if not notice_ts:
                logger.error(
                    f"Failed to post archive notice to channel {channel_id} "
                    f"(incident {link.incident.incident_number}), skipping archive"
                )
                errored += 1
                continue

            try:
                if not slack.archive_channel(channel_id):
                    raise RuntimeError(
                        f"archive_channel returned False for {channel_id}"
                    )
                archived += 1
                logger.info(
                    f"Archived stale channel {channel_id} "
                    f"(incident {link.incident.incident_number})"
                )
            except Exception:
                errored += 1
                logger.exception(
                    f"Failed to archive channel {channel_id} "
                    f"(incident {link.incident.incident_number}), "
                    f"deleting notice"
                )
                slack.delete_message(channel_id, notice_ts)
        except Exception:
            errored += 1
            logger.exception(
                f"Error processing channel {channel_id} "
                f"(incident {link.incident.incident_number})"
            )

    logger.info(
        f"archive_stale_channels complete: "
        f"scanned={scanned} archived={archived} skipped={skipped} errored={errored}"
    )


@datadog_log
def schedule_demo() -> None:
    incident = Incident.objects.order_by("-created_at").first()
    if incident:
        title = "Private Incident" if incident.is_private else incident.title
        logger.info(f"Most recent incident: INC-{incident.id}: {title}")
    else:
        logger.info("No incidents found.")
