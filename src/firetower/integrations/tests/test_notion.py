from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from firetower.integrations.services.notion import (
    NotionService,
    _build_slack_markdown,
    _users_cache,
)


@pytest.fixture
def notion():
    svc = NotionService(
        integration_token="test-key",
        database_id="db-id",
        template_markdown="# Template\n\nSome content.",
    )
    svc.client = MagicMock()
    return svc


class TestGetUsers:
    @pytest.fixture(autouse=True)
    def clear_users_cache(self):
        _users_cache.pop("test-key", None)
        yield
        _users_cache.pop("test-key", None)

    def test_returns_email_to_user_map(self, notion):
        notion.client.users.list.return_value = {
            "results": [
                {"person": {"email": "a@sentry.io"}, "name": "Alice", "id": "U1"},
                {"person": {"email": "b@sentry.io"}, "name": "Bob", "id": "U2"},
                {"object": "bot", "name": "Integrations", "id": "B1"},
            ],
            "next_cursor": None,
        }

        users = notion.get_users()

        assert users == {
            "a@sentry.io": {"name": "Alice", "id": "U1"},
            "b@sentry.io": {"name": "Bob", "id": "U2"},
        }

    def test_paginates_until_no_next_cursor(self, notion):
        notion.client.users.list.side_effect = [
            {
                "results": [{"person": {"email": "a@sentry.io"}, "name": "Alice", "id": "U1"}],
                "next_cursor": "cursor1",
            },
            {
                "results": [{"person": {"email": "b@sentry.io"}, "name": "Bob", "id": "U2"}],
                "next_cursor": None,
            },
        ]

        users = notion.get_users()

        assert len(users) == 2
        assert notion.client.users.list.call_count == 2
        notion.client.users.list.assert_any_call(page_size=100, start_cursor="cursor1")

    def test_caches_result_on_second_call(self, notion):
        notion.client.users.list.return_value = {"results": [], "next_cursor": None}

        notion.get_users()
        notion.get_users()

        notion.client.users.list.assert_called_once()

    def test_module_cache_shared_across_instances(self, notion):
        notion.client.users.list.return_value = {
            "results": [{"person": {"email": "a@sentry.io"}, "name": "Alice", "id": "U1"}],
            "next_cursor": None,
        }

        notion.get_users()

        second = NotionService(integration_token="test-key", database_id="db-id")
        second.client = MagicMock()
        second.get_users()

        second.client.users.list.assert_not_called()

    def test_retries_transient_errors_mid_pagination(self, notion):
        notion.client.users.list.side_effect = [
            {
                "results": [{"person": {"email": "a@sentry.io"}, "name": "Alice", "id": "U1"}],
                "next_cursor": "cursor1",
            },
            Exception("502 Bad Gateway"),
            {
                "results": [{"person": {"email": "b@sentry.io"}, "name": "Bob", "id": "U2"}],
                "next_cursor": None,
            },
        ]

        with patch("firetower.integrations.services.notion.time.sleep"):
            users = notion.get_users()

        assert len(users) == 2
        assert notion.client.users.list.call_count == 3

    def test_raises_after_max_retries(self, notion):
        notion.client.users.list.side_effect = [
            {"results": [], "next_cursor": "cursor1"},
            Exception("502"),
            Exception("502"),
            Exception("502"),
        ]

        with patch("firetower.integrations.services.notion.time.sleep"):
            with pytest.raises(Exception, match="502"):
                notion.get_users()


class TestSendMarkdown:
    def test_sends_insert_content_patch(self, notion):
        with patch("firetower.integrations.services.notion.httpx.patch") as mock_patch:
            mock_patch.return_value = MagicMock(status_code=200)
            mock_patch.return_value.raise_for_status = MagicMock()

            result = notion._send_markdown("page-id", "# Hello")

        assert result is True
        mock_patch.assert_called_once()
        call_kwargs = mock_patch.call_args
        assert "pages/page-id/markdown" in call_kwargs.args[0]
        assert call_kwargs.kwargs["json"] == {
            "type": "insert_content",
            "insert_content": {"content": "# Hello"},
        }

    def test_retries_on_failure_then_succeeds(self, notion):
        mock_response = MagicMock(status_code=200)
        mock_response.raise_for_status = MagicMock()

        with patch("firetower.integrations.services.notion.httpx.patch") as mock_patch:
            mock_patch.side_effect = [Exception("rate limited"), mock_response]

            with patch("firetower.integrations.services.notion.time.sleep"):
                result = notion._send_markdown("page-id", "content", max_retries=2)

        assert result is True
        assert mock_patch.call_count == 2

    def test_returns_false_after_max_retries(self, notion):
        with patch("firetower.integrations.services.notion.httpx.patch") as mock_patch:
            mock_patch.side_effect = Exception("always fails")

            with patch("firetower.integrations.services.notion.time.sleep"):
                result = notion._send_markdown("page-id", "content", max_retries=2)

        assert result is False
        assert mock_patch.call_count == 2


class TestApplyTemplate:
    def test_new_page_sends_template_then_slack(self, notion):
        with patch.object(notion, "_send_markdown", return_value=True) as mock_send:
            notion.apply_template("page-id", messages=[], update_slack=False)

        assert mock_send.call_count == 2
        template_call, slack_call = mock_send.call_args_list
        assert template_call.args[1] == "# Template\n\nSome content."
        assert "<details>" in slack_call.args[1]

    def test_update_slack_skips_template(self, notion):
        with patch.object(notion, "_send_markdown", return_value=True) as mock_send:
            notion.apply_template("page-id", messages=[], update_slack=True)

        assert mock_send.call_count == 1
        assert "<details>" in mock_send.call_args.args[1]

    def test_new_page_without_template_sends_only_slack(self):
        svc = NotionService(integration_token="test-key", database_id="db-id")
        svc.client = MagicMock()

        with patch.object(svc, "_send_markdown", return_value=True) as mock_send:
            svc.apply_template("page-id", messages=[], update_slack=False)

        assert mock_send.call_count == 1
        assert "<details>" in mock_send.call_args.args[1]


class TestBuildSlackMarkdown:
    def test_wraps_messages_in_toggle(self):
        messages = [
            {
                "author": "a@sentry.io",
                "date_time": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
                "text": "Hello world",
                "replies": [],
            }
        ]

        md = _build_slack_markdown(messages)

        assert md.startswith("<details>")
        assert md.endswith("</details>")
        assert "<summary>" in md
        assert "- [2024-01-15 10:30 UTC] a@sentry.io: Hello world" in md

    def test_indents_replies(self):
        messages = [
            {
                "author": "a@sentry.io",
                "date_time": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
                "text": "main",
                "replies": [
                    {
                        "author": "b@sentry.io",
                        "date_time": datetime(2024, 1, 15, 10, 31, tzinfo=UTC),
                        "text": "reply",
                    }
                ],
            }
        ]

        md = _build_slack_markdown(messages)

        lines = md.splitlines()
        main_line = next(l for l in lines if "main" in l)
        reply_line = next(l for l in lines if "reply" in l)
        assert main_line.startswith("- ")
        assert reply_line.startswith("  - ")

    def test_empty_messages_produces_empty_toggle(self):
        md = _build_slack_markdown([])

        assert "<details>" in md
        assert "</details>" in md
        assert "- " not in md
