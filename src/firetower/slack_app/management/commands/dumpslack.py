import logging
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from slack_sdk import WebClient

from firetower.incidents.models import ExternalLink, ExternalLinkType
from firetower.integrations.services.notion import NotionService
from firetower.slack_app.handlers.dumpslack import (
    _extract_notion_page_id,
    _get_channel_messages,
)
from firetower.slack_app.handlers.utils import get_incident_from_channel

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Trigger a Slack dump to Notion for a given channel (for local testing)"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("channel_id", help="Slack channel ID (e.g. C12345678)")

    def handle(self, *args: Any, **options: Any) -> None:
        channel_id = options["channel_id"]

        notion_config = settings.NOTION
        if not notion_config:
            raise CommandError("Notion integration is not configured in config.toml.")

        incident = get_incident_from_channel(channel_id)
        if not incident:
            raise CommandError(f"No incident found for channel {channel_id}.")

        self.stdout.write(f"Incident: {incident.incident_number} - {incident.title}")

        client = WebClient(token=settings.SLACK["BOT_TOKEN"])
        notion = NotionService(
            integration_token=notion_config["INTEGRATION_TOKEN"],
            database_id=notion_config["DATABASE_ID"],
            template_markdown=notion_config.get("TEMPLATE_MARKDOWN", ""),
        )

        existing_link = incident.external_links.filter(type=ExternalLinkType.NOTION).first()

        self.stdout.write("Fetching Slack messages...")
        messages = _get_channel_messages(client, channel_id)
        self.stdout.write(f"Fetched {len(messages)} messages.")

        if existing_link:
            page_id = _extract_notion_page_id(existing_link.url)
            if not page_id:
                raise CommandError(
                    f"Could not parse Notion page ID from stored URL: {existing_link.url}"
                )
            page_url = existing_link.url
            update_slack = True
            self.stdout.write(f"Updating existing page: {page_url}")
        else:
            base_url = settings.FIRETOWER_BASE_URL
            incident_url = f"{base_url}/{incident.incident_number}"
            captain_email = incident.captain.email if incident.captain else None

            self.stdout.write("Creating Notion page...")
            try:
                page = notion.create_postmortem_page(
                    incident_number=incident.incident_number,
                    incident_title=incident.title,
                    incident_url=incident_url,
                    incident_date=incident.created_at,
                    severity=incident.severity,
                    captain_email=captain_email,
                )
            except Exception as exc:
                raise CommandError(f"Failed to create Notion page: {exc}") from exc

            page_id = page["id"]
            page_url = page["url"]
            update_slack = False

            ExternalLink.objects.update_or_create(
                incident=incident,
                type=ExternalLinkType.NOTION,
                defaults={"url": page_url},
            )

        self.stdout.write("Dumping content to Notion...")
        try:
            notion.apply_template(page_id, messages, update_slack=update_slack)
        except Exception as exc:
            raise CommandError(f"Failed to populate Notion page: {exc}") from exc

        action = "Updated" if existing_link else "Created"
        self.stdout.write(self.style.SUCCESS(f"{action}: {page_url}"))
