import logging
import time

from django_q.tasks import Schedule

from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    IncidentStatus,
)
from firetower.incidents.tasks.decorators import datadog_log
from firetower.integrations.services.slack import SlackService

logger = logging.getLogger(__name__)

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

    terminal_statuses = [IncidentStatus.DONE, IncidentStatus.CANCELED]
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

            has_activity = False
            own_messages: list[dict] = []
            for page in slack.iter_channel_history(channel_id):
                for msg in page:
                    if msg.get("bot_id") != own_bot_id:
                        has_activity = True
                        break
                    own_messages.append(msg)
                if has_activity:
                    break
            if has_activity:
                skipped += 1
                continue

            for msg in own_messages:
                if msg.get("reply_count", 0) > 0:
                    replies = slack.get_thread_replies(channel_id, msg["ts"])
                    if replies:
                        has_activity = True
                        break
            if has_activity:
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
