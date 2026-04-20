import logging
import time
from datetime import UTC, datetime
from typing import Any

from notion_client import Client

logger = logging.getLogger(__name__)

_BLOCK_CHILD_LIMIT = 85  # Notion enforces 100; stay below for safety


class NotionService:
    def __init__(self, api_key: str, database_id: str, template_id: str = "") -> None:
        self.client: Client = Client(auth=api_key)
        self.database_id = database_id
        self.template_id = template_id
        self._users: dict[str, dict[str, str]] | None = None

    def get_users(self) -> dict[str, dict[str, str]]:
        """Return email -> {name, id} for all Notion workspace users."""
        if self._users is not None:
            return self._users

        users: dict[str, dict[str, str]] = {}
        start_cursor: str | None = None

        while True:
            kwargs: dict[str, Any] = {"page_size": 100}
            if start_cursor:
                kwargs["start_cursor"] = start_cursor
            response = self.client.users.list(**kwargs)
            for user in response.get("results", []):
                if "person" in user:
                    email = user["person"].get("email", "")
                    if email:
                        users[email] = {"name": user["name"], "id": user["id"]}
            start_cursor = response.get("next_cursor")
            if not start_cursor:
                break

        self._users = users
        return users

    def create_postmortem_page(
        self,
        incident_number: str,
        incident_title: str,
        incident_url: str,
        incident_date: datetime,
        severity: str | None = None,
        captain_email: str | None = None,
    ) -> dict[str, Any]:
        properties: dict[str, Any] = {
            "Name": {
                "title": [
                    {
                        "type": "text",
                        "text": {"content": f"[{incident_number}] {incident_title}"},
                    }
                ]
            },
            "Incident": {"url": incident_url},
            "Inc Date": {"date": {"start": incident_date.date().isoformat()}},
        }

        if severity:
            properties["Severity"] = {"select": {"name": severity}}

        if captain_email:
            notion_user = self.get_users().get(captain_email)
            if notion_user:
                properties["Incident Captain"] = {
                    "people": [{"object": "user", "id": notion_user["id"]}]
                }

        page: dict[str, Any] = self.client.pages.create(
            parent={"database_id": self.database_id},
            properties=properties,
        )
        return page

    def get_template_blocks(self) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        """Fetch template blocks one level deep. Returns (blocks, children_by_block_id)."""
        if not self.template_id:
            return [], {}

        response = self.client.blocks.children.list(block_id=self.template_id)
        blocks: list[dict[str, Any]] = []
        children: dict[str, list[dict[str, Any]]] = {}

        for block in response.get("results", []):
            if block.get("has_children"):
                child_resp = self.client.blocks.children.list(block_id=block["id"])
                children[block["id"]] = child_resp.get("results", [])
            blocks.append(block)

        return blocks, children

    def apply_template(
        self,
        page_id: str,
        template_blocks: list[dict[str, Any]],
        template_children: dict[str, list[dict[str, Any]]],
    ) -> None:
        """Copy template blocks onto the page."""
        blocks_to_append: list[dict[str, Any]] = []

        for block in template_blocks:
            block_type = block["type"]
            if block_type == "table":
                # The Notion API cannot duplicate tables directly; use a hardcoded postmortem schema.
                blocks_to_append.append(_standard_postmortem_table())
            else:
                stripped = _strip_block(block)
                if block["id"] in template_children:
                    stripped[block_type]["children"] = [
                        _strip_block(c) for c in template_children[block["id"]]
                    ]
                blocks_to_append.append(stripped)

        if blocks_to_append:
            self._append_children(page_id, blocks_to_append)

    def dump_slack_messages(
        self,
        page_id: str,
        messages: list[dict[str, Any]],
    ) -> None:
        """Append a collapsible Slack discussion section to the page."""
        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        toggle: dict[str, Any] = {
            "type": "toggle",
            "toggle": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": (
                                f"Slack channel discussions as of {timestamp}. "
                                "This should not be used in place of the Timeline."
                            )
                        },
                    }
                ],
                "color": "default",
                "children": [],
            },
        }

        response = self._append_children(page_id, [toggle])
        if not response:
            return

        toggle_id = next(
            (b["id"] for b in response.get("results", []) if b.get("type") == "toggle"),
            None,
        )
        if not toggle_id:
            logger.error("Could not find created toggle block ID")
            return

        message_blocks: list[dict[str, Any]] = []
        for msg in messages:
            message_blocks.append(_message_to_bullet(msg))
            message_blocks.extend(_message_to_bullet(r) for r in msg.get("replies", []))

        idx = 0
        while idx < len(message_blocks):
            self._append_children(toggle_id, message_blocks[idx : idx + _BLOCK_CHILD_LIMIT])
            idx += _BLOCK_CHILD_LIMIT

    def _append_children(
        self,
        block_id: str,
        children: list[dict[str, Any]],
        max_retries: int = 3,
    ) -> dict[str, Any] | None:
        for attempt in range(max_retries):
            try:
                result: dict[str, Any] = self.client.blocks.children.append(
                    block_id=block_id, children=children
                )
                return result
            except Exception as exc:
                wait = 2**attempt
                logger.warning(
                    "Notion append failed (attempt %d/%d): %s. Retrying in %ds.",
                    attempt + 1,
                    max_retries,
                    exc,
                    wait,
                )
                time.sleep(wait)

        logger.error("Max retries reached appending children to Notion block %s", block_id)
        return None


def _strip_block(block: dict[str, Any]) -> dict[str, Any]:
    """Return only the type key and its content dict, dropping all metadata."""
    block_type = block["type"]
    return {"type": block_type, block_type: block[block_type]}


def _message_to_bullet(msg: dict[str, Any]) -> dict[str, Any]:
    dt: datetime = msg["date_time"]
    author = msg.get("author") or "unknown"
    text = (msg.get("text") or "")[:2000]  # Notion rich_text limit
    content = f"[{dt.strftime('%Y-%m-%d %H:%M UTC')}] {author}: {text}"
    return {
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": content}}]
        },
    }


def _standard_postmortem_table() -> dict[str, Any]:
    """Five-column action items table used in standard postmortem docs."""
    headers = ["Priority", "Description", "Improvement/Prevention", "Owner", "Ticket URL"]
    return {
        "type": "table",
        "table": {
            "table_width": 5,
            "has_column_header": True,
            "has_row_header": False,
            "children": [
                {
                    "type": "table_row",
                    "table_row": {
                        "cells": [[{"type": "text", "text": {"content": h}}] for h in headers]
                    },
                },
                {"type": "table_row", "table_row": {"cells": [[], [], [], [], []]}},
                {"type": "table_row", "table_row": {"cells": [[], [], [], [], []]}},
            ],
        },
    }
