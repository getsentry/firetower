import logging
import time
from datetime import UTC, datetime
from typing import Any, cast

from notion_client import Client

logger = logging.getLogger(__name__)

_BLOCK_CHILD_LIMIT = 85  # Notion enforces a hard limit of 100; stay below for safety
_NOTION_RICH_TEXT_LIMIT = 2000


class NotionService:
    def __init__(self, integration_token: str, database_id: str, template_id: str = "") -> None:
        self.client: Client = Client(auth=integration_token, notion_version="2021-08-16")
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
            response = cast(dict[str, Any], self.client.users.list(**kwargs))
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

    def get_template_blocks(
        self,
    ) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        if not self.template_id:
            return [], {}

        blocks = self._fetch_all_children(self.template_id)
        children: dict[str, list[dict[str, Any]]] = {}
        for block in blocks:
            if block.get("has_children"):
                children[block["id"]] = self._fetch_all_children(block["id"])
        return blocks, children

    def _fetch_all_children(self, block_id: str) -> list[dict[str, Any]]:
        """Fetch all children of a block, handling pagination."""
        results: list[dict[str, Any]] = []
        start_cursor: str | None = None
        while True:
            kwargs: dict[str, Any] = {"block_id": block_id, "page_size": 100}
            if start_cursor:
                kwargs["start_cursor"] = start_cursor
            response = cast(dict[str, Any], self.client.blocks.children.list(**kwargs))
            results.extend(response.get("results", []))
            start_cursor = response.get("next_cursor")
            if not start_cursor:
                break
        return results

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

        logger.debug("Creating Notion page with database_id=%r", self.database_id)
        return cast(
            dict[str, Any],
            self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=properties,
            ),
        )

    def apply_template(
        self,
        page_id: str,
        template: list[dict[str, Any]],
        template_children: dict[str, list[dict[str, Any]]],
        messages: list[dict[str, Any]],
        update_slack: bool = False,
    ) -> None:
        if not update_slack:
            for block in template:
                if block["type"] == "table":
                    block_to_append: dict[str, Any] = _standard_postmortem_table()
                else:
                    block_to_append = _clean_block(block)
                response = self._append_children(page_id, [block_to_append])
                if block["type"] != "table" and block.get("id") in template_children:
                    if response is None:
                        logger.error(
                            "Failed to append template block %s, skipping children",
                            block.get("id"),
                        )
                        continue
                    cleaned = [_clean_block(b) for b in template_children[block["id"]]]
                    self._append_children(response["results"][0]["id"], cleaned)

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
        if response is None:
            logger.error(
                "Failed to append slack toggle to page %s, aborting slack dump", page_id
            )
            return
        toggle_id = response["results"][0]["id"]

        index = 0
        while index < len(messages):
            stopping_index, batch = _create_slack_content(messages, index)
            response = self._append_children(toggle_id, batch)
            if response is not None:
                slack_index = index
                notion_index = 0
                while (
                    slack_index < len(messages)
                    and notion_index < len(response["results"])
                ):
                    slack_msg = messages[slack_index]
                    if slack_msg.get("replies"):
                        reply_blocks = [_message_to_bullet(r) for r in slack_msg["replies"]]
                        self._append_children(
                            response["results"][notion_index]["id"], reply_blocks
                        )
                    slack_index += 1
                    notion_index += 1
            index = stopping_index

    def _append_children(
        self,
        block_id: str,
        children: list[dict[str, Any]],
        max_retries: int = 3,
    ) -> dict[str, Any] | None:
        for attempt in range(max_retries):
            try:
                return cast(
                    dict[str, Any],
                    self.client.blocks.children.append(
                        block_id=block_id, children=children
                    ),
                )
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
        logger.error(
            "Max retries reached appending children to Notion block %s", block_id
        )
        return None


def _clean_block(block: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in block.items() if k not in ("archived", "in_trash")}


def _create_slack_content(
    messages: list[dict[str, Any]], starting_index: int
) -> tuple[int, list[dict[str, Any]]]:
    bullets: list[dict[str, Any]] = []
    index = starting_index
    while index < len(messages) and len(bullets) < _BLOCK_CHILD_LIMIT:
        bullets.append(_message_to_bullet(messages[index]))
        index += 1
    return index, bullets


def _message_to_bullet(msg: dict[str, Any]) -> dict[str, Any]:
    dt: datetime = msg["date_time"]
    author = msg.get("author") or "unknown"
    text = msg.get("text") or ""
    content = f"[{dt.strftime('%Y-%m-%d %H:%M UTC')}] {author}: {text}"[
        :_NOTION_RICH_TEXT_LIMIT
    ]
    return {
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": content}}]
        },
    }


def _standard_postmortem_table() -> dict[str, Any]:
    headers = [
        "Priority",
        "Description",
        "Improvement/Prevention",
        "Owner",
        "Ticket URL",
    ]
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
                        "cells": [
                            [{"type": "text", "text": {"content": h}}] for h in headers
                        ]
                    },
                },
                {"type": "table_row", "table_row": {"cells": [[], [], [], [], []]}},
                {"type": "table_row", "table_row": {"cells": [[], [], [], [], []]}},
            ],
        },
    }
