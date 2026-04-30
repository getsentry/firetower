from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
import requests

from firetower.integrations.services.genai import GenAIService, _detect_location
from firetower.integrations.services.notion import (
    NotionService,
    _convert_markdown_to_notion_blocks,
    _parse_timestamps_to_rich_text,
)


class TestParseTimestampsToRichText:
    def test_plain_text_no_timestamps(self):
        result = _parse_timestamps_to_rich_text("no timestamps here")
        assert result == [{"type": "text", "text": {"content": "no timestamps here"}}]

    def test_bracketed_timestamp(self):
        result = _parse_timestamps_to_rich_text("[2024-01-15 14:30 UTC] event occurred")
        assert result[0] == {
            "type": "mention",
            "mention": {"type": "date", "date": {"start": "2024-01-15T14:30:00Z"}},
        }
        assert result[1] == {"type": "text", "text": {"content": " event occurred"}}

    def test_timestamp_with_seconds(self):
        result = _parse_timestamps_to_rich_text("[2024-01-15 14:30:45 UTC] event")
        assert result[0]["mention"]["date"]["start"] == "2024-01-15T14:30:45Z"

    def test_unbracketed_timestamp_returned_as_plain_text(self):
        # Unbracketed timestamps are not converted — brackets must be balanced.
        result = _parse_timestamps_to_rich_text("Started: 2024-01-15 14:30 UTC")
        assert result == [{"type": "text", "text": {"content": "Started: 2024-01-15 14:30 UTC"}}]

    def test_empty_string(self):
        result = _parse_timestamps_to_rich_text("")
        assert result == [{"type": "text", "text": {"content": ""}}]


class TestConvertMarkdownToNotionBlocks:
    def test_heading(self):
        blocks = _convert_markdown_to_notion_blocks("## Timeline")
        assert len(blocks) == 1
        assert blocks[0]["type"] == "heading_2"
        assert blocks[0]["heading_2"]["rich_text"] == [
            {"type": "text", "text": {"content": "Timeline"}}
        ]

    def test_dash_bullet(self):
        blocks = _convert_markdown_to_notion_blocks("- some event")
        assert blocks[0]["type"] == "bulleted_list_item"
        assert blocks[0]["bulleted_list_item"]["rich_text"] == [
            {"type": "text", "text": {"content": "some event"}}
        ]

    def test_bullet_with_timestamp(self):
        blocks = _convert_markdown_to_notion_blocks("- [2024-01-15 14:30 UTC] - event")
        block = blocks[0]
        assert block["type"] == "bulleted_list_item"
        rich_text = block["bulleted_list_item"]["rich_text"]
        assert rich_text[0]["type"] == "mention"
        assert rich_text[0]["mention"]["date"]["start"] == "2024-01-15T14:30:00Z"

    def test_star_and_bullet_variants(self):
        md = "* item one\n- item two\n• item three"
        blocks = _convert_markdown_to_notion_blocks(md)
        assert all(b["type"] == "bulleted_list_item" for b in blocks)
        assert len(blocks) == 3

    def test_paragraph(self):
        blocks = _convert_markdown_to_notion_blocks("plain text line")
        assert blocks[0]["type"] == "paragraph"

    def test_empty_lines_skipped(self):
        blocks = _convert_markdown_to_notion_blocks("## A\n\n## B")
        assert len(blocks) == 2

    def test_full_timeline(self):
        md = (
            "## Timeline\n"
            "- [2024-01-15 14:30 UTC] - Incident started\n"
            "- [2024-01-15 14:45 UTC] - Root cause identified\n"
            "\n"
            "## Key Timestamps\n"
            "- Started: [2024-01-15 14:30 UTC]\n"
            "- Resolved: N/A\n"
        )
        blocks = _convert_markdown_to_notion_blocks(md)
        assert blocks[0]["type"] == "heading_2"
        assert blocks[1]["type"] == "bulleted_list_item"
        assert blocks[2]["type"] == "bulleted_list_item"
        assert blocks[3]["type"] == "heading_2"
        assert blocks[4]["type"] == "bulleted_list_item"
        assert blocks[5]["type"] == "bulleted_list_item"


class TestAddTimelineToPage:
    @pytest.fixture
    def notion(self):
        svc = NotionService(
            integration_token="test-key",
            database_id="db-id",
        )
        svc.client = MagicMock()
        return svc

    def test_appends_toggle_then_timeline_blocks(self, notion):
        toggle_id = "toggle-block-id"
        notion.client.blocks.children.append.return_value = {
            "results": [{"id": toggle_id}]
        }

        notion.add_timeline_to_page("page-id", "## Timeline\n- [2024-01-15 14:30 UTC] - event")

        calls = notion.client.blocks.children.append.call_args_list
        assert len(calls) == 2
        # First call creates the toggle on the page
        first_call = calls[0]
        assert first_call.kwargs["block_id"] == "page-id"
        toggle = first_call.kwargs["children"][0]
        assert toggle["type"] == "toggle"
        assert len(toggle["toggle"]["children"]) == 1  # callout only
        assert toggle["toggle"]["children"][0]["type"] == "callout"
        # Second call appends timeline blocks to the toggle
        second_call = calls[1]
        assert second_call.kwargs["block_id"] == toggle_id

    def test_raises_if_toggle_append_fails(self, notion):
        notion.client.blocks.children.append.return_value = None

        with pytest.raises(RuntimeError, match="Failed to append AI timeline toggle"):
            notion.add_timeline_to_page("page-id", "## Timeline\n- event")

    def test_batches_many_blocks(self, notion):
        notion.client.blocks.children.append.return_value = {
            "results": [{"id": "toggle-id"}]
        }
        # 90 bullet lines -> should exceed _BLOCK_CHILD_LIMIT (85) and batch
        md = "\n".join(f"- line {i}" for i in range(90))

        notion.add_timeline_to_page("page-id", md)

        calls = notion.client.blocks.children.append.call_args_list
        # toggle create + 2 batches (85 + 5)
        assert len(calls) == 3


class TestDetectLocation:
    def test_parses_region_from_metadata_server(self):
        mock_resp = MagicMock()
        mock_resp.text = "projects/123456789/regions/us-east1"
        with patch("firetower.integrations.services.genai.requests.get", return_value=mock_resp):
            assert _detect_location() == "us-east1"

    def test_falls_back_to_default_when_metadata_unavailable(self):
        with patch(
            "firetower.integrations.services.genai.requests.get",
            side_effect=requests.exceptions.ConnectionError,
        ):
            assert _detect_location() == "us-central1"

    def test_falls_back_on_non_200(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError
        with patch("firetower.integrations.services.genai.requests.get", return_value=mock_resp):
            assert _detect_location() == "us-central1"


class TestGenAIService:
    @pytest.fixture
    def genai_service(self):
        with patch("firetower.integrations.services.genai.GenAIService.__init__", return_value=None):
            svc = GenAIService.__new__(GenAIService)
            svc._model = "gemini-2.5-flash"
            svc._client = MagicMock()
            return svc

    def _make_messages(self, n=2):
        return [
            {
                "author": f"user{i}@sentry.io",
                "date_time": datetime(2024, 1, 15, 14, i, 0, tzinfo=UTC),
                "text": f"Message {i}",
                "replies": [],
                "images": [],
            }
            for i in range(n)
        ]

    def test_returns_timeline_text(self, genai_service):
        genai_service._client.models.generate_content.return_value = MagicMock(
            text="## Timeline\n- [2024-01-15 14:00 UTC] - event"
        )
        result = genai_service.generate_timeline(self._make_messages())
        assert result is not None
        assert "Timeline" in result

    def test_returns_none_for_empty_messages(self, genai_service):
        result = genai_service.generate_timeline([])
        assert result is None
        genai_service._client.models.generate_content.assert_not_called()

    def test_returns_none_on_empty_response(self, genai_service):
        genai_service._client.models.generate_content.return_value = MagicMock(text=None)
        result = genai_service.generate_timeline(self._make_messages())
        assert result is None

    def test_returns_none_on_exception(self, genai_service):
        genai_service._client.models.generate_content.side_effect = RuntimeError("API down")
        result = genai_service.generate_timeline(self._make_messages())
        assert result is None

    def test_includes_incident_summary_in_prompt(self, genai_service):
        genai_service._client.models.generate_content.return_value = MagicMock(text="timeline")
        genai_service.generate_timeline(self._make_messages(), incident_summary="DB outage")
        call_args = genai_service._client.models.generate_content.call_args
        assert "DB outage" in call_args.kwargs["contents"]

    def test_includes_thread_replies_skipping_parent(self, genai_service):
        genai_service._client.models.generate_content.return_value = MagicMock(text="t")
        messages = [
            {
                "author": "a@sentry.io",
                "date_time": datetime(2024, 1, 15, 14, 0, tzinfo=UTC),
                "text": "parent",
                "replies": [
                    # index 0 is parent duplicate - should be skipped
                    {"author": "a@sentry.io", "date_time": datetime(2024, 1, 15, 14, 0, tzinfo=UTC), "text": "parent"},
                    {"author": "b@sentry.io", "date_time": datetime(2024, 1, 15, 14, 1, tzinfo=UTC), "text": "reply"},
                ],
                "images": [],
            }
        ]
        genai_service.generate_timeline(messages)
        contents = genai_service._client.models.generate_content.call_args.kwargs["contents"]
        assert "reply" in contents
        # parent text appears once (as the main message), not twice
        assert contents.count("parent") == 1
