"""Recovery sweep for incidents that could not reach Linear on declare.

When Linear is unavailable during an incident declaration the handler creates a
degraded ``inc-tmp-<hash>`` channel and records a :class:`PendingIncident` (the
DB is up, only Linear is down). This scheduled sweep finalizes those rows into
real incidents once Linear recovers -- allocating an id, adopting/creating the
Linear parent, renaming the channel to ``inc-<id>`` and populating it -- with no
human re-entry. It also retroactively repairs incidents that ended up with no
Linear parent (e.g. old backfills, or a populate that failed after adoption).
"""

import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone

from firetower.auth.services import get_or_create_user_from_slack_id
from firetower.incidents.allocation import (
    LinearUnavailable,
    _looks_like_placeholder,
    adopt_on_create_enabled,
)
from firetower.incidents.hooks import (
    _get_channel_id,
    _get_linear_service,
    create_linear_parent_issue,
    populate_linear_parent,
)
from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentStatus,
    PendingIncident,
)
from firetower.incidents.serializers import IncidentWriteSerializer
from firetower.incidents.tasks.decorators import datadog_log
from firetower.integrations.services import SlackService

logger = logging.getLogger(__name__)
_slack_service = SlackService()

# Only repair missing Linear parents on reasonably recent incidents so the sweep
# does not endlessly retry ancient rows that will never get a parent.
RECOVERY_REPAIR_MAX_AGE_DAYS = 14


def _finalize_pending_incident(pending: PendingIncident, client: Any) -> None:
    """Turn one :class:`PendingIncident` into a real incident (idempotent).

    Leaves the row in place (to retry next sweep) if Linear is still
    unavailable; deletes it once the incident is created or if the channel is
    already linked to an incident.
    """
    channel_id = pending.slack_channel_id

    existing_link = ExternalLink.objects.filter(
        type=ExternalLinkType.SLACK,
        url__endswith=f"/archives/{channel_id}",
    ).first()
    if existing_link:
        # Already finalized (e.g. via `/ft backfill`); drop the stale row.
        pending.delete()
        return

    reporter = (
        get_or_create_user_from_slack_id(pending.reporter_slack_id)
        if pending.reporter_slack_id
        else None
    )
    if not reporter:
        logger.warning(
            "Cannot finalize pending incident %s: reporter %s not resolvable",
            channel_id,
            pending.reporter_slack_id,
        )
        return

    captain_email = reporter.email
    if pending.captain_slack_id:
        captain_user = get_or_create_user_from_slack_id(pending.captain_slack_id)
        if captain_user:
            captain_email = captain_user.email

    channel_url = _slack_service.build_channel_url(channel_id)
    data: dict[str, Any] = {
        "title": pending.title,
        "severity": pending.severity,
        "description": pending.description,
        "impact_summary": pending.impact_summary,
        "captain": captain_email,
        "reporter": reporter.email,
        "is_private": pending.is_private,
        "external_links": {"slack": channel_url},
    }

    serializer = IncidentWriteSerializer(data=data, context={"skip_hooks": True})
    if not serializer.is_valid():
        logger.error(
            "Pending incident %s failed validation on finalize: %s",
            channel_id,
            serializer.errors,
        )
        return

    try:
        incident = serializer.save()
    except LinearUnavailable:
        logger.info(
            "Linear still unavailable; leaving pending incident %s for next sweep",
            channel_id,
        )
        return

    # skip_hooks=True means the populate path never runs via the hook. Populate
    # the adopted Linear parent here so finalized incidents get their parent too.
    if adopt_on_create_enabled() and incident.linear_parent_issue_id:
        identity = getattr(incident, "_allocated_identity", None)
        if identity is not None:
            try:
                populate_linear_parent(
                    incident, identity.linear_url, channel_id=channel_id
                )
            except Exception:
                logger.exception(
                    "Failed to populate Linear parent for finalized incident %s",
                    incident.id,
                )

    # Rename inc-tmp-<hash> -> inc-<id>, set topic/bookmark, sync participants.
    from firetower.slack_app.handlers.backfill_incident import (  # noqa: PLC0415
        _setup_channel_for_incident,
    )

    _setup_channel_for_incident(incident, channel_id, pending.reporter_slack_id, client)

    pending.delete()
    logger.info(
        "Finalized pending incident %s -> %s", channel_id, incident.incident_number
    )


def ensure_linear_parent_for_incident(incident: Incident) -> None:
    """Best-effort ensure ``incident`` has a Linear parent issue.

    Never clobbers a moved/aliased/foreign issue: when identifiers are synced we
    only adopt a clean, still-matching ``INC-N`` placeholder (otherwise we leave
    the incident for a human). When identifiers are not synced, numbers need not
    match, so a fresh titled issue is minted via the standard create path.
    """
    if incident.linear_parent_issue_id:
        return

    linear_config = settings.LINEAR
    if not linear_config or not linear_config.get("TEAM_ID"):
        return

    channel_id: str | None = None
    try:
        channel_id = _get_channel_id(incident)
    except Exception:
        logger.exception("Failed to resolve channel id for incident %s", incident.id)

    if not linear_config.get("SYNC_IDENTIFIERS"):
        create_linear_parent_issue(incident, channel_id=channel_id)
        return

    identifier = incident.incident_number
    linear = _get_linear_service()
    try:
        issue = linear.get_issue(identifier)
    except Exception:
        logger.exception("Failed to look up %s while repairing parent", identifier)
        return

    if not issue or issue.get("identifier") != identifier:
        logger.info(
            "No matching Linear placeholder for %s; skipping parent repair",
            identifier,
        )
        return
    if not _looks_like_placeholder(issue):
        logger.warning(
            "Refusing to adopt non-placeholder issue at %s during parent repair",
            identifier,
        )
        return
    if (
        Incident.objects.exclude(pk=incident.pk)
        .filter(linear_parent_issue_id=issue["id"])
        .exists()
    ):
        logger.warning(
            "Placeholder %s already adopted by another incident; skipping",
            identifier,
        )
        return

    incident.linear_parent_issue_id = issue["id"]
    incident.save(update_fields=["linear_parent_issue_id"])
    populate_linear_parent(incident, issue["url"], channel_id=channel_id)
    logger.info("Repaired Linear parent for %s", identifier)


def _repair_missing_parents() -> None:
    if not settings.LINEAR or not settings.LINEAR.get("TEAM_ID"):
        return

    cutoff = timezone.now() - timedelta(days=RECOVERY_REPAIR_MAX_AGE_DAYS)
    incidents = Incident.objects.filter(
        linear_parent_issue_id__isnull=True,
        created_at__gte=cutoff,
    ).exclude(status=IncidentStatus.CANCELED)

    for incident in incidents:
        try:
            ensure_linear_parent_for_incident(incident)
        except Exception:
            logger.exception(
                "Failed to repair Linear parent for incident %s", incident.id
            )


@datadog_log
def sweep_incident_recovery() -> None:
    """Finalize pending incidents and repair incidents missing a Linear parent."""
    client = None
    try:
        from firetower.slack_app.bolt import get_bolt_app  # noqa: PLC0415

        client = get_bolt_app().client
    except Exception:
        logger.exception("Failed to get Slack client for incident recovery sweep")

    if client is not None:
        for pending in PendingIncident.objects.all():
            try:
                _finalize_pending_incident(pending, client)
            except Exception:
                logger.exception(
                    "Failed to finalize pending incident %s", pending.slack_channel_id
                )

    _repair_missing_parents()
