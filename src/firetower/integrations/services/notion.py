import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, cast

from notion_client import Client

logger = logging.getLogger(__name__)

_BLOCK_CHILD_LIMIT = 85  # Notion enforces 100; stay below for safety
_NOTION_PAGE_CREATE_LIMIT = 100  # max children in pages.create
_TEMPLATE_FETCH_WORKERS = 3  # stay comfortably under Notion's 3 req/s rate limit


class NotionService:
    def __init__(self, integration_token: str, database_id: str, template_id: str = "") -> None:
        self.client: Client = Client(auth=integration_token)
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
        """Fetch template blocks one level deep, parallelizing child requests."""
        if not self.template_id:
            return [], {}

        blocks = self._fetch_all_children(self.template_id)

        blocks_with_children = [b for b in blocks if b.get("has_children")]
        children: dict[str, list[dict[str, Any]]] = {}

        if blocks_with_children:

            def _fetch_children(
                block: dict[str, Any],
            ) -> tuple[str, list[dict[str, Any]]]:
                return block["id"], self._fetch_all_children(block["id"])

            with ThreadPoolExecutor(max_workers=_TEMPLATE_FETCH_WORKERS) as pool:
                children = dict(pool.map(_fetch_children, blocks_with_children))

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
        template_blocks: list[dict[str, Any]] | None = None,
        template_children: dict[str, list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        """Create postmortem page, optionally embedding template blocks in the same API call."""
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

        create_kwargs: dict[str, Any] = {
            "parent": {"database_id": self.database_id},
            "properties": properties,
        }

        overflow: list[dict[str, Any]] = []
        if template_blocks:
            all_blocks = _build_appendable_blocks(
                template_blocks, template_children or {}
            )
            create_kwargs["children"] = all_blocks[:_NOTION_PAGE_CREATE_LIMIT]
            overflow = all_blocks[_NOTION_PAGE_CREATE_LIMIT:]

        logger.debug("Creating Notion page with database_id=%r", self.database_id)
        page = cast(dict[str, Any], self.client.pages.create(**create_kwargs))

        if overflow:
            self._append_children(page["id"], overflow)

        return page

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
            self._append_children(
                toggle_id, message_blocks[idx : idx + _BLOCK_CHILD_LIMIT]
            )
            idx += _BLOCK_CHILD_LIMIT

    def _append_children(
        self,
        block_id: str,
        children: list[dict[str, Any]],
        max_retries: int = 3,
    ) -> dict[str, Any] | None:
        for attempt in range(max_retries):
            try:
                result = cast(
                    dict[str, Any],
                    self.client.blocks.children.append(
                        block_id=block_id, children=children
                    ),
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

        logger.error(
            "Max retries reached appending children to Notion block %s", block_id
        )
        return None


def _build_appendable_blocks(
    template_blocks: list[dict[str, Any]],
    template_children: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Convert template blocks into the stripped form required by the Notion append API."""
    result: list[dict[str, Any]] = []
    for block in template_blocks:
        block_type = block["type"]
        if block_type == "table":
            # The Notion API cannot duplicate tables directly; use a hardcoded postmortem schema.
            result.append(_standard_postmortem_table())
        else:
            stripped = _strip_block(block)
            if block["id"] in template_children:
                stripped[block_type]["children"] = [
                    _strip_block(c) for c in template_children[block["id"]]
                ]
            result.append(stripped)
    return result


def _strip_block(block: dict[str, Any]) -> dict[str, Any]:
    """Return only the type key and its content dict, dropping all metadata."""
    block_type = block["type"]
    return {"type": block_type, block_type: block[block_type]}


_NOTION_RICH_TEXT_LIMIT = 2000


def _message_to_bullet(msg: dict[str, Any]) -> dict[str, Any]:
    dt: datetime = msg["date_time"]
    author = msg.get("author") or "unknown"
    text = msg.get("text") or ""
    # Truncate the full content string — the prefix adds ~40 chars before the message text.
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
    """Five-column action items table used in standard postmortem docs."""
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
