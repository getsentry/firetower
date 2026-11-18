import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from firetower.incidents.hooks import get_slack_user_id
from firetower.incidents.models import (
    ExternalLinkType,
    Incident,
    IncidentStatus,
    TimelineEventType,
)
from firetower.incidents.tasks.decorators import datadog_log
from firetower.integrations.services.slack import SlackReadError, SlackService

logger = logging.getLogger(__name__)

STALE_STATUS_BUSINESS_DAYS = 1
QUIET_CHANNEL_BUSINESS_DAYS = 1
NUDGE_EVERY_BUSINESS_DAYS = 3

NUDGE_TIMEZONE = ZoneInfo("America/Los_Angeles")

HUMAN_MESSAGE_SUBTYPES = {None, "thread_broadcast", "file_share"}

STALE_INCIDENT_NUDGE_MESSAGE = (
    "{ic_mention}This incident has been *{status}* since {status_since}, and "
    "nobody has posted here for {quiet_days}.\n"
    "If it's fixed, run {commands}. If work is still ongoing, a short update "
    "here helps."
)


def subtract_business_days(moment: datetime, days: int) -> datetime:
    """Return the time `days` weekdays (Mon–Fri, in `moment`'s timezone) before `moment`."""
    result = moment
    remaining = days
    while remaining > 0:
        result -= timedelta(days=1)
        if result.weekday() < 5:
            remaining -= 1
    return result


def count_business_days(start: datetime, end: datetime) -> int:
    """Return how many whole weekdays (Mon–Fri, in `start`'s timezone) have passed from `start` to `end`."""
    days = 0
    cursor = start + timedelta(days=1)
    while cursor <= end:
        if cursor.weekday() < 5:
            days += 1
        cursor += timedelta(days=1)
    return days


def _is_human_message(message: dict[str, Any]) -> bool:
    return (
        message.get("type") == "message"
        and bool(message.get("user"))
        and not message.get("bot_id")
        and message.get("subtype") in HUMAN_MESSAGE_SUBTYPES
    )


def _ts_to_datetime(ts: str) -> datetime:
    return datetime.fromtimestamp(float(ts), tz=UTC)


def _last_human_activity(
    slack: SlackService,
    channel_id: str,
    history: list[dict[str, Any]],
    quiet_cutoff: datetime,
) -> datetime | None:
    """Return the latest human post in the channel history or its threads.

    Replies are only fetched for threads with a reply after `quiet_cutoff`.
    For older threads, `latest_reply` is used as an upper bound. Raises
    SlackReadError if a thread can't be read.
    """
    latest: datetime | None = None
    for message in history:
        candidates: list[datetime] = []
        if _is_human_message(message) and message.get("ts"):
            candidates.append(_ts_to_datetime(message["ts"]))
        latest_reply = message.get("latest_reply")
        if latest_reply:
            latest_reply_at = _ts_to_datetime(latest_reply)
            if latest_reply_at <= quiet_cutoff:
                candidates.append(latest_reply_at)
            else:
                candidates.extend(
                    _ts_to_datetime(reply["ts"])
                    for reply in slack.get_thread_replies(
                        channel_id, message["ts"], raise_on_error=True
                    )
                )
        for candidate in candidates:
            if latest is None or candidate > latest:
                latest = candidate
    return latest


def _last_status_change(incident: Incident) -> datetime:
    occurred_at = (
        incident.timeline_events.filter(event_type=TimelineEventType.STATUS_CHANGED)
        .order_by("-occurred_at")
        .values_list("occurred_at", flat=True)
        .first()
    )
    return occurred_at or incident.created_at


def _build_message(incident: Incident, status_since: datetime, quiet_days: int) -> str:
    slash_command = settings.SLACK.get("SLASH_COMMAND", "/inc")
    if incident.status == IncidentStatus.ACTIVE:
        commands = f"`{slash_command} mitigated` or `{slash_command} resolved`"
    else:
        commands = f"`{slash_command} resolved`"

    captain_slack_id = get_slack_user_id(incident.captain) if incident.captain else None
    return STALE_INCIDENT_NUDGE_MESSAGE.format(
        ic_mention=f"<@{captain_slack_id}> " if captain_slack_id else "",
        status=incident.status,
        status_since=status_since.astimezone(NUDGE_TIMEZONE).strftime("%a %b %-d"),
        quiet_days=f"{quiet_days} business day{'' if quiet_days == 1 else 's'}",
        commands=commands,
    )


@datadog_log
def send_stale_incident_nudges() -> None:
    """Nudge the captain of each Active or Mitigated incident that looks forgotten.

    An incident is forgotten when its status has not changed for
    STALE_STATUS_BUSINESS_DAYS and nobody has posted in its channel for
    QUIET_CHANNEL_BUSINESS_DAYS. Each incident gets at most one nudge every
    NUDGE_EVERY_BUSINESS_DAYS. Runs hourly; nudges only go out on weekdays
    in NUDGE_TIMEZONE.
    """
    if not settings.SLACK.get("STALE_INCIDENT_NUDGES_ENABLED"):
        return

    now = timezone.now().astimezone(NUDGE_TIMEZONE)
    if now.weekday() >= 5:
        return

    stale_cutoff = subtract_business_days(now, STALE_STATUS_BUSINESS_DAYS)
    quiet_cutoff = subtract_business_days(now, QUIET_CHANNEL_BUSINESS_DAYS)
    nudge_cutoff = subtract_business_days(now, NUDGE_EVERY_BUSINESS_DAYS)

    slack = SlackService()
    incidents = Incident.objects.filter(
        status__in=[IncidentStatus.ACTIVE, IncidentStatus.MITIGATED],
        is_private=False,
    ).select_related("captain")

    for incident in incidents:
        if incident.last_nudge_at and incident.last_nudge_at > nudge_cutoff:
            continue

        status_since = _last_status_change(incident)
        if status_since > stale_cutoff:
            continue

        slack_link = incident.external_links.filter(type=ExternalLinkType.SLACK).first()
        channel_id = (
            slack.parse_channel_id_from_url(slack_link.url) if slack_link else None
        )
        if not channel_id:
            continue

        history = slack.get_channel_history(channel_id)
        if not history:
            logger.info(
                "No channel history for %s, skipping stale incident nudge",
                incident.incident_number,
            )
            continue
        try:
            last_activity = _last_human_activity(
                slack, channel_id, history, quiet_cutoff
            )
        except SlackReadError:
            logger.info(
                "Couldn't read threads for %s, skipping stale incident nudge",
                incident.incident_number,
            )
            continue
        quiet_since = max(
            last_activity or incident.created_at, incident.created_at
        ).astimezone(NUDGE_TIMEZONE)
        if quiet_since > quiet_cutoff:
            continue

        message = _build_message(
            incident, status_since, count_business_days(quiet_since, now)
        )
        if slack.post_message(channel_id, message) is None:
            logger.info(
                "Failed to post stale incident nudge for %s",
                incident.incident_number,
            )
            continue

        Incident.objects.filter(pk=incident.pk).update(last_nudge_at=now)
        logger.info("Posted stale incident nudge for %s", incident.incident_number)
