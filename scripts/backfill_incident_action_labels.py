"""Backfill incident-action labels without changing issues' other fields.

Preview: uv run python scripts/backfill_incident_action_labels.py
Apply:   uv run python scripts/backfill_incident_action_labels.py --apply
"""

import argparse
import logging
import os

import django
from django.conf import settings

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply label additions")
    args = parser.parse_args(argv)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "firetower.settings")
    django.setup()

    from firetower.incidents.models import Incident  # noqa: PLC0415
    from firetower.integrations.services.linear import (  # noqa: PLC0415
        INCIDENT_ACTION_LABEL_NAME,
        LinearService,
    )

    if not settings.LINEAR:
        parser.error("Linear integration is not configured")

    service = LinearService()
    label_id = service.get_issue_label_id(INCIDENT_ACTION_LABEL_NAME)
    if not label_id:
        logger.error("Workspace label %s is unavailable", INCIDENT_ACTION_LABEL_NAME)
        return 1

    incidents = Incident.objects.exclude(linear_parent_issue_id__isnull=True).exclude(
        linear_parent_issue_id=""
    )
    seen: set[str] = set()
    missing = added = failed = 0
    for incident in incidents.iterator():
        children = service.get_child_issues(
            incident.linear_parent_issue_id, include_archived=True
        )
        if children is None:
            logger.error(
                "Failed to fetch children for incident %s", incident.incident_number
            )
            failed += 1
            continue
        for issue in children:
            if issue["id"] in seen:
                continue
            seen.add(issue["id"])
            if label_id in issue.get("label_ids", []):
                continue
            missing += 1
            logger.info(
                "%s %s to %s",
                "Adding" if args.apply else "Would add",
                INCIDENT_ACTION_LABEL_NAME,
                issue["identifier"],
            )
            if args.apply:
                if service.add_issue_label(issue["id"], label_id):
                    added += 1
                else:
                    logger.error("Failed to label %s", issue["identifier"])
                    failed += 1

    logger.info(
        "%s: %d checked, %d missing labels, %d added, %d failures",
        "Backfill" if args.apply else "Dry run",
        len(seen),
        missing,
        added,
        failed,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
