"""
One-off script to import Jira incidents into Firetower's database.

Pulls from the PROD Jira project (INC). Field IDs sourced from opsbot's
Config(Environment.PROD).

Usage:
    python scripts/import_jira_incidents.py [--dry-run] [--batch-size N]

Run from the repo root with the virtualenv active and a valid config.toml in place.
"""

import argparse
import logging
import os
import sys

# Bootstrap Django before importing models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "firetower.settings")

import django

django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.db import transaction  # noqa: E402
from django.utils.dateparse import parse_datetime  # noqa: E402

from firetower.incidents.models import (  # noqa: E402
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from firetower.integrations.services.jira import JiraService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# This script is specifically for the PROD incident project.
JIRA_PROJECT_KEY = "INC"

STATUSPAGE_BASE_URL = "https://status.sentry.io/incidents/"

# Custom field IDs from opsbot Config(Environment.PROD)
FIELD_POSTMORTEM = "customfield_10943"
FIELD_TIME_STARTED = "customfield_11032"
FIELD_TIME_DETECTED = "customfield_11026"
FIELD_TIME_ANALYZED = "customfield_11718"  # called TIME_CLUE in opsbot
FIELD_TIME_MITIGATED = "customfield_11027"
FIELD_TIME_RECOVERED = "customfield_11719"  # called TIME_RECOVERY in opsbot
FIELD_STATUSPAGE_ID = "customfield_11017"

JIRA_TO_FIRETOWER_STATUS: dict[str, str] = {
    "Active": IncidentStatus.ACTIVE,
    "Mitigated": IncidentStatus.MITIGATED,
    "Postmortem": IncidentStatus.POSTMORTEM,
    "Done": IncidentStatus.DONE,
    "Cancelled": IncidentStatus.CANCELLED,
}

VALID_SEVERITIES = {s.value for s in IncidentSeverity}


def fetch_all_issues(jira_service: JiraService, batch_size: int) -> list[dict]:
    """Fetch all INC issues from Jira using pagination."""
    all_issues = []
    start_at = 0
    jql = f'project = "{JIRA_PROJECT_KEY}" ORDER BY created DESC'

    while True:
        batch = jira_service.client.search_issues(
            jql, startAt=start_at, maxResults=batch_size
        )
        for issue in batch:
            fields = issue.fields

            def get_field(field_id: str) -> str | None:
                return getattr(fields, field_id, None) or None

            statuspage_id = get_field(FIELD_STATUSPAGE_ID)
            statuspage_url = (
                f"{STATUSPAGE_BASE_URL}{statuspage_id}" if statuspage_id else None
            )

            all_issues.append(
                {
                    "key": issue.key,
                    "title": fields.summary,
                    "description": getattr(fields, "description", "") or "",
                    "status": fields.status.name,
                    "severity": jira_service._extract_severity(issue),
                    "assignee_email": fields.assignee.emailAddress
                    if fields.assignee
                    else None,
                    "reporter_email": fields.reporter.emailAddress
                    if fields.reporter
                    else None,
                    "created_at": fields.created,
                    # Milestone timestamps
                    "time_started": get_field(FIELD_TIME_STARTED),
                    "time_detected": get_field(FIELD_TIME_DETECTED),
                    "time_analyzed": get_field(FIELD_TIME_ANALYZED),
                    "time_mitigated": get_field(FIELD_TIME_MITIGATED),
                    "time_recovered": get_field(FIELD_TIME_RECOVERED),
                    # External links
                    "postmortem_url": get_field(FIELD_POSTMORTEM),
                    "statuspage_url": statuspage_url,
                }
            )

        if len(batch) < batch_size:
            break
        start_at += batch_size

    return all_issues


def get_or_create_user(email: str) -> User:
    user, created = User.objects.get_or_create(
        email=email,
        defaults={"username": email, "is_active": True},
    )
    if created:
        logger.info("  Created user for %s", email)
    return user


def import_incident(issue: dict, jira_domain: str, dry_run: bool) -> str:
    """Import a single Jira incident. Returns 'created' or 'skipped'."""
    jira_key = issue["key"]
    jira_url = f"{jira_domain}/browse/{jira_key}"

    if ExternalLink.objects.filter(type=ExternalLinkType.JIRA, url=jira_url).exists():
        return "skipped"

    severity = issue["severity"]
    if not severity or severity not in VALID_SEVERITIES:
        logger.warning(
            "  %s: unrecognised severity %r, defaulting to P3", jira_key, severity
        )
        severity = IncidentSeverity.P3

    status = JIRA_TO_FIRETOWER_STATUS.get(issue["status"])
    if status is None:
        logger.warning(
            "  %s: unmapped status %r, defaulting to Done", jira_key, issue["status"]
        )
        status = IncidentStatus.DONE

    reporter = (
        get_or_create_user(issue["reporter_email"]) if issue["reporter_email"] else None
    )
    captain = (
        get_or_create_user(issue["assignee_email"]) if issue["assignee_email"] else None
    )

    if dry_run:
        return "created"

    with transaction.atomic():
        incident = Incident(
            title=issue["title"],
            description=issue["description"],
            status=status,
            severity=severity,
            reporter=reporter,
            captain=captain,
            time_started=parse_datetime(issue["time_started"]) if issue["time_started"] else None,
            time_detected=parse_datetime(issue["time_detected"]) if issue["time_detected"] else None,
            time_analyzed=parse_datetime(issue["time_analyzed"]) if issue["time_analyzed"] else None,
            time_mitigated=parse_datetime(issue["time_mitigated"]) if issue["time_mitigated"] else None,
            time_recovered=parse_datetime(issue["time_recovered"]) if issue["time_recovered"] else None,
        )
        incident.save()

        # Preserve original Jira creation time (auto_now_add prevents direct assignment)
        created_at = parse_datetime(issue["created_at"])
        if created_at:
            Incident.objects.filter(pk=incident.pk).update(created_at=created_at)

        # External links
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.JIRA,
            url=jira_url,
        )
        if issue["statuspage_url"]:
            ExternalLink.objects.create(
                incident=incident,
                type=ExternalLinkType.STATUSPAGE,
                url=issue["statuspage_url"],
            )
        if issue["postmortem_url"]:
            ExternalLink.objects.create(
                incident=incident,
                type=ExternalLinkType.NOTION,
                url=issue["postmortem_url"],
            )

    return "created"


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Jira INC incidents into Firetower")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the import without writing to the database",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of issues to fetch per Jira API request (default: 100)",
    )
    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN — no changes will be written")

    jira_service = JiraService()

    if jira_service.project_key != JIRA_PROJECT_KEY:
        logger.error(
            "config.toml project_key is %r but this script only runs against %r. "
            "Make sure you're using the PROD config.",
            jira_service.project_key,
            JIRA_PROJECT_KEY,
        )
        sys.exit(1)

    logger.info("Fetching incidents from Jira project %s...", JIRA_PROJECT_KEY)
    issues = fetch_all_issues(jira_service, args.batch_size)
    logger.info("Found %d incidents in Jira", len(issues))

    imported = skipped = failed = 0
    for issue in issues:
        key = issue["key"]
        try:
            result = import_incident(issue, jira_service.domain, args.dry_run)
            if result == "created":
                imported += 1
                logger.info("  Imported %s", key)
            else:
                skipped += 1
                logger.info("  Skipped %s (already exists)", key)
        except Exception:
            failed += 1
            logger.exception("  Failed to import %s", key)

    logger.info(
        "\nDone. Imported: %d  Skipped: %d  Failed: %d", imported, skipped, failed
    )


if __name__ == "__main__":
    main()
