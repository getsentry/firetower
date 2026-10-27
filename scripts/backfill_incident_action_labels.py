"""Backfill incident-action labels without changing issues' other fields.

Preview: uv run python scripts/backfill_incident_action_labels.py
Apply:   uv run python scripts/backfill_incident_action_labels.py --apply
"""

import argparse
import logging
import os

import django
from django.conf import settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply label additions")
    args = parser.parse_args(argv)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "firetower.settings")
    django.setup()

    from firetower.incidents.models import Incident  # noqa: PLC0415
    from firetower.incidents.services import backfill_action_item_labels  # noqa: PLC0415

    if not settings.LINEAR:
        parser.error("Linear integration is not configured")

    stats = backfill_action_item_labels(Incident.objects.all(), dry_run=not args.apply)
    for error in stats.errors:
        logging.getLogger(__name__).error("%s", error)
    return 1 if stats.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
