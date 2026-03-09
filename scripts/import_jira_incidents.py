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
import re
import sys

# Bootstrap Django before importing models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "firetower.settings")

import django

django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.db import transaction  # noqa: E402
from django.utils.dateparse import parse_datetime  # noqa: E402
from jira import JIRA  # noqa: E402

from firetower.incidents.models import (  # noqa: E402
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    Tag,
    TagType,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# This script is specifically for the PROD incident project.
JIRA_PROJECT_KEY = "INC"

STATUSPAGE_BASE_URL = "https://status.sentry.io/incidents/"

# Custom field IDs from opsbot Config(Environment.PROD)
# Jira field name          -> customfield ID       -> Firetower field
FIELD_SEVERITY = "customfield_10941"        # Severity             -> Incident.severity (P0–P4)
FIELD_TYPE = "customfield_11008"            # Incident Type        -> (not stored directly)
FIELD_IMPACT = "customfield_11031"          # Impact               -> Incident.impact_type_tags + downtime check
FIELD_SERVICE_TIER = "customfield_11033"    # Service Tier         -> Incident.service_tier (T0–T4)
FIELD_POSTMORTEM = "customfield_10943"      # Postmortem URL       -> ExternalLink(NOTION)
FIELD_TIME_STARTED = "customfield_11032"    # Time Started         -> Incident.time_started
FIELD_TIME_DETECTED = "customfield_11026"   # Time Detected        -> Incident.time_detected
FIELD_TIME_ANALYZED = "customfield_11718"   # Time Clue (opsbot)   -> Incident.time_analyzed
FIELD_TIME_MITIGATED = "customfield_11027"  # Time Mitigated       -> Incident.time_mitigated
FIELD_TIME_RECOVERED = "customfield_11719"  # Time Recovery (opsbot) -> Incident.time_recovered
FIELD_STATUSPAGE_ID = "customfield_11017"   # Statuspage ID        -> ExternalLink(STATUSPAGE)

# Jira status -> Firetower IncidentStatus
JIRA_TO_FIRETOWER_STATUS: dict[str, str] = {
    "Active": IncidentStatus.ACTIVE,
    "Mitigated": IncidentStatus.MITIGATED,
    "Postmortem": IncidentStatus.POSTMORTEM,
    "Actions Pending": IncidentStatus.POSTMORTEM,
    "Done": IncidentStatus.DONE,
    "Cancelled": IncidentStatus.CANCELLED,
}

VALID_SEVERITIES = {s.value for s in IncidentSeverity}

# Jira service tier values (may come as "0"–"4" or "T0"–"T4") -> Firetower Incident.service_tier
JIRA_SERVICE_TIER_MAP: dict[str, str] = {
    "0": "T0",
    "1": "T1",
    "2": "T2",
    "3": "T3",
    "4": "T4",
    "T0": "T0",
    "T1": "T1",
    "T2": "T2",
    "T3": "T3",
    "T4": "T4",
}

# Jira issue label -> Firetower AFFECTED_REGION tag name
JIRA_LABEL_TO_REGION: dict[str, str] = {
    "multi-tenant-us": "us",
    "multi-tenant-de": "de",
    "geico": "geico",
    "disney": "disney",
    "ly-corp": "ly",
    "goldman-sachs": "goldman-sachs",
}


def build_jira_client() -> tuple[JIRA, str]:
    """Build a Jira client from environment variables. Returns (client, domain)."""
    domain = os.environ.get("JIRA_DOMAIN", "https://getsentry.atlassian.net")
    account = os.environ.get("JIRA_ACCOUNT")
    api_key = os.environ.get("JIRA_API_KEY")

    if not account or not api_key:
        logger.error("JIRA_ACCOUNT and JIRA_API_KEY environment variables must be set.")
        sys.exit(1)

    client = JIRA(domain, basic_auth=(account, api_key))
    return client, domain


def _resolve_email(user) -> str | None:
    """Return the email for a Jira user, constructing one from display name if missing."""
    if user is None:
        return None
    email = getattr(user, "emailAddress", None)
    if email:
        return email
    display_name = getattr(user, "displayName", None)
    if display_name:
        parts = display_name.lower().split()
        return f"{parts[0]}.{parts[-1]}@sentry.io"
    return None


def fetch_all_issues(client: JIRA, batch_size: int) -> list[dict]:
    """Fetch all INC issues from Jira using pagination."""
    all_issues = []
    next_page_token = None
    jql = f'project = "{JIRA_PROJECT_KEY}" ORDER BY created DESC'

    while True:
        batch = client.enhanced_search_issues(
            jql, nextPageToken=next_page_token, maxResults=batch_size
        )
        for issue in batch:
            fields = issue.fields

            def get_field(field_id: str) -> str | None:
                return getattr(fields, field_id, None) or None

            severity_field = getattr(fields, FIELD_SEVERITY, None)
            severity = getattr(severity_field, "value", None)

            type_field = getattr(fields, FIELD_TYPE, None)
            incident_type = getattr(type_field, "value", None)

            impact_field = getattr(fields, FIELD_IMPACT, None) if FIELD_IMPACT else None
            incident_impact = getattr(impact_field, "value", None)

            service_tier_field = getattr(fields, FIELD_SERVICE_TIER, None)
            service_tier_raw = getattr(service_tier_field, "value", None)
            service_tier = JIRA_SERVICE_TIER_MAP.get(service_tier_raw) if service_tier_raw else None

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
                    "severity": severity,
                    "type": incident_type,
                    "assignee_email": _resolve_email(fields.assignee),
                    "reporter_email": _resolve_email(fields.reporter),
                    "impact": incident_impact,
                    "service_tier": service_tier,
                    "labels": list(getattr(fields, "labels", []) or []),
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

        next_page_token = batch.nextPageToken
        if not next_page_token:
            break

    return all_issues


def get_or_create_user(email: str) -> User:
    user, created = User.objects.get_or_create(
        email=email,
        defaults={"username": email, "is_active": True},
    )
    if created:
        logger.info("  Created user for %s", email)
    return user


def resolve_region_tags(labels: list[str]) -> list[Tag]:
    """Map Jira labels to existing affected region Tag objects."""
    tags = []
    for label in labels:
        region_name = JIRA_LABEL_TO_REGION.get(label)
        if region_name:
            tag = Tag.objects.filter(
                name__iexact=region_name,
                type=TagType.AFFECTED_REGION,
            ).first()
            if tag:
                tags.append(tag)
            else:
                logger.warning("  Label %r mapped to %r but no matching region tag found", label, region_name)
    return tags


def resolve_service_tags(labels: list[str], title: str) -> list[Tag]:
    """Match Jira labels and title against existing AFFECTED_SERVICE Tag objects.

    - Labels: exact case-insensitive match against tag names.
    - Title: word-boundary case-insensitive search for each tag name.
    """
    all_service_tags = {tag.name.lower(): tag for tag in Tag.objects.filter(type=TagType.AFFECTED_SERVICE)}

    matched: dict[int, Tag] = {}

    for label in labels:
        tag = all_service_tags.get(label.lower())
        if tag:
            matched[tag.id] = tag

    title_lower = title.lower()
    for name_lower, tag in all_service_tags.items():
        if re.search(r"\b" + re.escape(name_lower) + r"\b", title_lower):
            matched[tag.id] = tag

    return list(matched.values())


def compute_downtime_minutes(issue: dict) -> int | None:
    """
    Return downtime in minutes if the incident qualifies, otherwise None.

    Criteria (all must be true):
      - impact == "Availability"   (FIELD_IMPACT / customfield_11031)
      - statuspage_url is set      (FIELD_STATUSPAGE_ID / customfield_11017)
      - time_started is present    (FIELD_TIME_STARTED / customfield_11032)
      - time_mitigated is present  (FIELD_TIME_MITIGATED / customfield_11027)

    Result: floor((time_mitigated - time_started).total_seconds() / 60)
    """
    started = parse_datetime(issue["time_started"]) if issue["time_started"] else None
    mitigated = parse_datetime(issue["time_mitigated"]) if issue["time_mitigated"] else None

    if (
        issue["impact"] == "Availability"
        and issue["statuspage_url"]
        and started
        and mitigated
    ):
        delta = mitigated - started
        return max(0, int(delta.total_seconds() // 60))

    return None


def import_incident(issue: dict, jira_domain: str, dry_run: bool) -> str:
    """Import a single Jira incident. Returns 'created' or 'skipped'."""
    jira_key = issue["key"]
    jira_url = f"{jira_domain}/browse/{jira_key}"

    jira_id = int(jira_key.split("-")[1])
    if Incident.objects.filter(pk=jira_id).exists():
        logger.error("  %s: incident with id %d already exists, skipping", jira_key, jira_id)
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
    captain = get_or_create_user(issue["assignee_email"]) if issue["assignee_email"] else None

    total_downtime = compute_downtime_minutes(issue)
    mapped_regions = [
        JIRA_LABEL_TO_REGION[label]
        for label in issue["labels"]
        if label in JIRA_LABEL_TO_REGION
    ]
    service_tags = resolve_service_tags(issue["labels"], issue["title"])

    if dry_run:
        def fmt_dt(val: str | None) -> str:
            return parse_datetime(val).strftime("%Y-%m-%d %H:%M") if val else "—"

        downtime_str = "—"
        if total_downtime is not None:
            hours, mins = divmod(total_downtime, 60)
            downtime_str = f"{hours}h {mins}m ({total_downtime} min)" if hours else f"{mins}m ({total_downtime} min)"

        service_names = ", ".join(sorted(t.name for t in service_tags)) if service_tags else "—"
        logger.info(
            "  %s | status=%-10s severity=%s tier=%-3s type=%-14s impact=%-14s captain=%-30s reporter=%-30s "
            "started=%-16s detected=%-16s analyzed=%-16s mitigated=%-16s recovered=%-16s "
            "downtime=%-16s statuspage=%-3s postmortem=%-3s regions=%-20s services=%s",
            jira_key,
            status,
            severity,
            issue["service_tier"] or "—",
            issue["type"] or "—",
            issue["impact"] or "—",
            issue["assignee_email"] or "—",
            issue["reporter_email"] or "—",
            fmt_dt(issue["time_started"]),
            fmt_dt(issue["time_detected"]),
            fmt_dt(issue["time_analyzed"]),
            fmt_dt(issue["time_mitigated"]),
            fmt_dt(issue["time_recovered"]),
            downtime_str,
            "yes" if issue["statuspage_url"] else "no",
            "yes" if issue["postmortem_url"] else "no",
            ", ".join(mapped_regions) if mapped_regions else "—",
            service_names,
        )
        return "created"

    with transaction.atomic():
        incident = Incident(
            id=jira_id,
            title=issue["title"],
            description=issue["description"],
            status=status,
            severity=severity,
            reporter=reporter,
            captain=captain,
            total_downtime=total_downtime,
            service_tier=issue["service_tier"],
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

        region_tags = resolve_region_tags(issue["labels"])
        if region_tags:
            incident.affected_region_tags.set(region_tags)

        if service_tags:
            incident.affected_service_tags.set(service_tags)

        if issue["impact"]:
            impact_tag = Tag.objects.filter(
                name__iexact=issue["impact"],
                type=TagType.IMPACT_TYPE,
            ).first()
            if impact_tag:
                incident.impact_type_tags.set([impact_tag])
            else:
                logger.warning(
                    "  %s: unrecognised impact type %r, skipping impact tag",
                    issue["key"],
                    issue["impact"],
                )

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

    client, domain = build_jira_client()

    logger.info("Fetching incidents from Jira project %s...", JIRA_PROJECT_KEY)
    issues = fetch_all_issues(client, args.batch_size)
    logger.info("Found %d incidents in Jira", len(issues))

    imported = skipped = failed = 0
    for issue in issues:
        key = issue["key"]
        try:
            result = import_incident(issue, domain, args.dry_run)
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
