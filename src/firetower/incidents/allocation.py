"""Incident id allocation.

The default (flag-off) path mints ids from the local :class:`IncidentCounter`
and lets the Linear parent be claimed/created afterwards by the incident hook.

When ``INCIDENT_ADOPT_ON_CREATE`` is enabled (and ``SYNC_IDENTIFIERS`` is set),
ids are minted by adopting a *matching* ``INC-N`` placeholder in Linear: we walk
the counter forward, claiming a clean matching placeholder or creating a new one
and adopting whatever id Linear mints. The incident's numeric id and its Linear
parent are therefore always allocated together, and we never claim an issue whose
identifier does not match the id we hand out (which is what let the legacy
``claim_linear_issue`` path clobber moved/aliased issues).
"""

import logging
import os
from dataclasses import dataclass

from datadog import statsd
from django.conf import settings
from django.db import connection, transaction
from django.db.models import Max

from firetower.incidents.models import (
    INCIDENT_ID_START,
    Incident,
    IncidentCounter,
    get_next_incident_id,
)
from firetower.integrations.services.linear import (
    LinearError,
    LinearService,
    parse_project_number,
)

logger = logging.getLogger(__name__)

METRIC_PREFIX = "firetower.inc_alloc"

# Title used for placeholder issues minted by the allocator.
PLACEHOLDER_TITLE = "Placeholder"

# Upper bound on how many aliased / used / stray ``INC-N`` slots we skip before
# giving up on claiming and falling through to create-and-adopt.
MAX_ALIAS_SKIPS = 25


@dataclass(frozen=True)
class AllocatedIdentity:
    """The result of allocating an incident id.

    ``linear_issue_uuid``/``linear_url`` are empty strings on the flag-off path,
    meaning "no pre-claimed Linear parent" — the legacy hook path applies.
    """

    inc_id: int
    linear_issue_uuid: str
    linear_url: str


class LinearUnavailable(Exception):
    """Raised when the adopt-on-create allocator cannot reach Linear.

    The surrounding ``transaction.atomic()`` rolls back, so the incident counter
    is not advanced. Callers route to a degraded path rather than hard-failing.
    """


def adopt_on_create_enabled() -> bool:
    return bool(
        settings.LINEAR
        and settings.LINEAR.get("SYNC_IDENTIFIERS")
        and settings.LINEAR.get("INCIDENT_ADOPT_ON_CREATE")
    )


def _looks_like_placeholder(issue: dict[str, object]) -> bool:
    """Conservatively decide whether ``issue`` is a claimable placeholder.

    Only issues whose title matches the placeholder title are claimable;
    anything else is a "stray" real issue we must not touch.
    """
    return issue.get("title") == PLACEHOLDER_TITLE


def _ensure_incident_counter() -> None:
    """Self-heal a missing counter row, mirroring ``get_next_incident_id``."""
    if IncidentCounter.objects.filter(pk=1).exists():
        return
    max_id = Incident.objects.aggregate(max_id=Max("id"))["max_id"]
    IncidentCounter.objects.get_or_create(
        pk=1,
        defaults={"next_id": (max_id + 1) if max_id else INCIDENT_ID_START},
    )


def _create_and_adopt_placeholder(
    linear: LinearService, team_id: str, project_id: str | None
) -> tuple[int, str, str]:
    """Create a placeholder issue in Linear and adopt whatever id it minted.

    Side-effect free with respect to the DB and counter (no writes, no counter
    mutation) so a future buffer-refill job can reuse it. Raises
    :class:`LinearUnavailable` if the create fails or Linear minted an
    identifier that is not ``INC-<int>`` (e.g. the team was renamed).
    """
    issue = linear.create_issue(PLACEHOLDER_TITLE, "", team_id, project_id)
    if not issue:
        logger.warning("Failed to create Linear placeholder issue for allocation")
        statsd.increment(f"{METRIC_PREFIX}.unavailable")
        raise LinearUnavailable
    minted = parse_project_number(issue["identifier"])
    if minted is None:
        logger.error(
            "Linear minted a non-%s identifier for a placeholder issue: %s",
            settings.PROJECT_KEY,
            issue["identifier"],
        )
        statsd.increment(f"{METRIC_PREFIX}.unavailable")
        raise LinearUnavailable
    return minted, issue["id"], issue["url"]


def allocate_incident_identity() -> AllocatedIdentity:
    """Allocate the next incident id (and, when adopting, its Linear parent)."""
    if not adopt_on_create_enabled():
        return AllocatedIdentity(get_next_incident_id(), "", "")

    assert settings.LINEAR is not None
    team_id = str(settings.LINEAR.get("TEAM_ID", ""))
    project_id = str(settings.LINEAR.get("PROJECT_ID", "")) or None

    _ensure_incident_counter()
    linear = LinearService.for_allocation()

    # The counter row lock must be held only across the Linear calls and released
    # when this atomic() commits, *before* the slow channel-setup work runs. That
    # only holds if this is the outermost transaction: nested inside an enclosing
    # atomic() the lock would instead be held until the outer commit. Assert the
    # invariant as a regression tripwire. pytest wraps every test in a
    # transaction, so skip the check there.
    assert "PYTEST_CURRENT_TEST" in os.environ or not connection.in_atomic_block, (
        "allocate_incident_identity() must run outside an enclosing transaction "
        "so the counter lock is released before slow channel work"
    )

    # ATOMIC_REQUESTS is off and neither creation entry point wraps create() in a
    # transaction, so this atomic() is its own transaction: the row lock is held
    # across the Linear calls (intended — it serializes concurrent allocations)
    # and released when we return. On LinearUnavailable the block rolls back, so
    # the counter is not advanced.
    with statsd.timed(f"{METRIC_PREFIX}.duration"), transaction.atomic():
        counter = IncidentCounter.objects.select_for_update().get(pk=1)
        n = counter.next_id
        for _ in range(MAX_ALIAS_SKIPS):
            identifier = f"{settings.PROJECT_KEY}-{n}"
            try:
                issue = linear.get_issue(identifier, raise_on_error=True)
            except LinearError:
                logger.warning("Linear unavailable while allocating %s", identifier)
                statsd.increment(f"{METRIC_PREFIX}.unavailable")
                raise LinearUnavailable from None

            if issue is None:
                minted, uuid, url = _create_and_adopt_placeholder(
                    linear, team_id, project_id
                )
                if minted < n:
                    logger.error(
                        "Linear minted id %s below the counter position %s; "
                        "refusing to allocate",
                        minted,
                        n,
                    )
                    statsd.increment(f"{METRIC_PREFIX}.unavailable")
                    raise LinearUnavailable
                counter.next_id = minted + 1
                counter.save(update_fields=["next_id"])
                statsd.increment(f"{METRIC_PREFIX}.create_adopt")
                return AllocatedIdentity(minted, uuid, url)

            if issue["identifier"] != identifier:
                # INC-n was moved/aliased to another team (e.g. PRODENG-1404);
                # skip it rather than clobber it.
                n += 1
                counter.next_id = n
                statsd.increment(f"{METRIC_PREFIX}.alias_skip")
                continue

            if Incident.objects.filter(pk=n).exists():
                n += 1
                counter.next_id = n
                statsd.increment(f"{METRIC_PREFIX}.used_skip")
                continue

            if not _looks_like_placeholder(issue):
                logger.error(
                    "Skipping stray non-placeholder issue at %s while allocating",
                    identifier,
                )
                n += 1
                counter.next_id = n
                statsd.increment(f"{METRIC_PREFIX}.stray")
                continue

            counter.next_id = n + 1
            counter.save(update_fields=["next_id"])
            statsd.increment(f"{METRIC_PREFIX}.claim")
            return AllocatedIdentity(n, issue["id"], issue["url"])

        # Skip budget exhausted — fall through to create-and-adopt.
        minted, uuid, url = _create_and_adopt_placeholder(linear, team_id, project_id)
        if minted < n:
            logger.error(
                "Linear minted id %s below the counter position %s; "
                "refusing to allocate",
                minted,
                n,
            )
            statsd.increment(f"{METRIC_PREFIX}.unavailable")
            raise LinearUnavailable
        counter.next_id = minted + 1
        counter.save(update_fields=["next_id"])
        statsd.increment(f"{METRIC_PREFIX}.create_adopt")
        return AllocatedIdentity(minted, uuid, url)
