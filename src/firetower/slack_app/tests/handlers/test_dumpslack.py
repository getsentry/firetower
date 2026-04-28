from unittest.mock import MagicMock, patch

from firetower.slack_app.handlers.dumpslack import (
    _download_image,
    _extract_image_urls,
    _extract_notion_page_id,
    _get_channel_messages,
    _is_slack_url,
    handle_dumpslack_command,
)


class TestExtractNotionPageId:
    def test_extracts_id_without_hyphens(self):
        url = "https://www.notion.so/sentry/Title-abc123def456abc123def456abc123de"
        result = _extract_notion_page_id(url)
        assert result == "abc123de-f456-abc1-23de-f456abc123de"

    def test_extracts_uuid_with_hyphens(self):
        url = "https://www.notion.so/abc123de-f456-abc1-23de-f456abc123de"
        result = _extract_notion_page_id(url)
        assert result == "abc123de-f456-abc1-23de-f456abc123de"

    def test_returns_none_for_invalid_url(self):
        assert _extract_notion_page_id("https://notion.so/no-id-here") is None


def _make_users_list_response(members: list[dict] | None = None) -> dict:
    """Return a users_list response with the given members (or a default single user)."""
    if members is None:
        members = [
            {
                "id": "U1",
                "deleted": False,
                "is_bot": False,
                "profile": {"email": "user@sentry.io"},
            }
        ]
    return {"ok": True, "members": members, "response_metadata": {"next_cursor": ""}}


class TestGetChannelMessages:
    def test_filters_bots_and_system_messages(self):
        mock_client = MagicMock()
        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "user": "U1",
                    "text": "real message",
                    "ts": "1000000000.000000",
                },
                {
                    "type": "message",
                    "user": "U2",
                    "text": "bot msg",
                    "ts": "1000000001.000000",
                    "bot_id": "B1",
                },
                {
                    "type": "message",
                    "user": "U3",
                    "text": "joined",
                    "ts": "1000000002.000000",
                    "subtype": "channel_join",
                },
                {"type": "message", "user": "U4", "ts": "1000000003.000000"},  # no text
            ],
        }
        mock_client.users_list.return_value = _make_users_list_response()

        messages = _get_channel_messages(mock_client, "C123")

        assert len(messages) == 1
        assert messages[0]["text"] == "real message"

    def test_returns_chronological_order(self):
        mock_client = MagicMock()
        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "user": "U1",
                    "text": "second",
                    "ts": "1000000002.000000",
                },
                {
                    "type": "message",
                    "user": "U1",
                    "text": "first",
                    "ts": "1000000001.000000",
                },
            ],
        }
        mock_client.users_list.return_value = _make_users_list_response()

        messages = _get_channel_messages(mock_client, "C123")

        assert messages[0]["text"] == "first"
        assert messages[1]["text"] == "second"

    def test_returns_empty_on_api_error(self):
        mock_client = MagicMock()
        mock_client.conversations_history.side_effect = Exception("api error")

        messages = _get_channel_messages(mock_client, "C123")

        assert messages == []

    def test_fetches_thread_replies(self):
        mock_client = MagicMock()
        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "user": "U1",
                    "text": "parent",
                    "ts": "1000000001.000000",
                    "thread_ts": "1000000001.000000",
                    "reply_count": 1,
                },
            ],
        }
        mock_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "user": "U1",
                    "text": "parent",
                    "ts": "1000000001.000000",
                },
                {
                    "type": "message",
                    "user": "U2",
                    "text": "reply",
                    "ts": "1000000002.000000",
                },
            ],
        }
        mock_client.users_list.return_value = _make_users_list_response(
            members=[
                {
                    "id": "U1",
                    "deleted": False,
                    "is_bot": False,
                    "profile": {"email": "u1@sentry.io"},
                },
                {
                    "id": "U2",
                    "deleted": False,
                    "is_bot": False,
                    "profile": {"email": "u2@sentry.io"},
                },
            ]
        )

        messages = _get_channel_messages(mock_client, "C123")

        assert len(messages) == 1
        assert len(messages[0]["replies"]) == 1
        assert messages[0]["replies"][0]["text"] == "reply"

    def test_falls_back_to_users_info_for_cache_miss(self):
        mock_client = MagicMock()
        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "user": "U_UNKNOWN",
                    "text": "hello",
                    "ts": "1000000001.000000",
                },
            ],
        }
        # users_list returns no members, so U_UNKNOWN is a cache miss
        mock_client.users_list.return_value = _make_users_list_response(members=[])
        mock_client.users_info.return_value = {
            "user": {"profile": {"email": "fallback@sentry.io"}}
        }

        messages = _get_channel_messages(mock_client, "C123")

        assert len(messages) == 1
        assert messages[0]["author"] == "fallback@sentry.io"
        mock_client.users_info.assert_called_once_with(user="U_UNKNOWN")


class TestExtractImageUrls:
    def test_extracts_attachment_image_url_with_source(self):
        msg = {
            "attachments": [
                {
                    "image_url": "https://p.datadoghq.com/img/graph.png",
                    "title_link": "https://app.datadoghq.com/dashboard/abc",
                }
            ]
        }
        assert _extract_image_urls(msg) == [
            {
                "image_url": "https://p.datadoghq.com/img/graph.png",
                "source_url": "https://app.datadoghq.com/dashboard/abc",
            }
        ]

    def test_falls_back_to_from_url_when_no_title_link(self):
        msg = {
            "attachments": [
                {
                    "image_url": "https://p.datadoghq.com/img/graph.png",
                    "from_url": "https://app.datadoghq.com/dashboard/xyz",
                }
            ]
        }
        result = _extract_image_urls(msg)
        assert result[0]["source_url"] == "https://app.datadoghq.com/dashboard/xyz"

    def test_source_url_empty_when_no_link_fields(self):
        msg = {"attachments": [{"image_url": "https://p.datadoghq.com/img/graph.png"}]}
        result = _extract_image_urls(msg)
        assert result == [{"image_url": "https://p.datadoghq.com/img/graph.png", "source_url": ""}]

    def test_extracts_slack_file_url_with_empty_source(self):
        msg = {
            "files": [
                {
                    "mimetype": "image/png",
                    "url_private": "https://files.slack.com/files-pri/T1/screenshot.png",
                }
            ]
        }
        assert _extract_image_urls(msg) == [
            {
                "image_url": "https://files.slack.com/files-pri/T1/screenshot.png",
                "source_url": "",
            }
        ]

    def test_skips_non_image_files(self):
        msg = {"files": [{"mimetype": "application/pdf", "url_private": "https://files.slack.com/doc.pdf"}]}
        assert _extract_image_urls(msg) == []

    def test_skips_attachments_without_image_url(self):
        msg = {"attachments": [{"text": "some text", "fallback": "fallback"}]}
        assert _extract_image_urls(msg) == []

    def test_returns_empty_for_message_with_no_attachments_or_files(self):
        msg = {"text": "hello", "user": "U1"}
        assert _extract_image_urls(msg) == []


class TestIsSlackUrl:
    def test_matches_files_slack_com(self):
        assert _is_slack_url("https://files.slack.com/files-pri/T1/img.jpg") is True

    def test_matches_slack_com_subdomain(self):
        assert _is_slack_url("https://slack-edge.com/img.png") is False
        assert _is_slack_url("https://something.slack.com/path") is True

    def test_rejects_slack_com_in_path(self):
        assert _is_slack_url("https://evil.com/slack.com/img.png") is False

    def test_rejects_slack_com_as_subdomain_of_attacker(self):
        assert _is_slack_url("https://slack.com.evil.com/img.png") is False

    def test_rejects_non_slack_url(self):
        assert _is_slack_url("https://p.datadoghq.com/img/graph.png") is False


class TestDownloadImage:
    def test_downloads_external_image_without_auth(self):
        mock_response = MagicMock()
        mock_response.content = b"PNG_DATA"
        mock_response.headers = {"content-type": "image/png"}
        mock_response.raise_for_status = MagicMock()

        with patch("firetower.slack_app.handlers.dumpslack.httpx.get", return_value=mock_response) as mock_get:
            result = _download_image("https://p.datadoghq.com/img/graph.png", "xoxb-token")

        assert result == (b"PNG_DATA", "image/png")
        call_headers = mock_get.call_args.kwargs["headers"]
        assert "Authorization" not in call_headers

    def test_adds_slack_bearer_token_for_slack_urls(self):
        mock_response = MagicMock()
        mock_response.content = b"IMG"
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.raise_for_status = MagicMock()

        with patch("firetower.slack_app.handlers.dumpslack.httpx.get", return_value=mock_response) as mock_get:
            _download_image("https://files.slack.com/files-pri/T1/img.jpg", "xoxb-token")

        call_headers = mock_get.call_args.kwargs["headers"]
        assert call_headers["Authorization"] == "Bearer xoxb-token"

    def test_returns_none_on_request_failure(self):
        with patch("firetower.slack_app.handlers.dumpslack.httpx.get", side_effect=Exception("timeout")):
            result = _download_image("https://example.com/img.png", "token")

        assert result is None

    def test_returns_none_for_non_image_content_type(self):
        mock_response = MagicMock()
        mock_response.content = b"<html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()

        with patch("firetower.slack_app.handlers.dumpslack.httpx.get", return_value=mock_response):
            result = _download_image("https://example.com/page", "token")

        assert result is None


class TestHandleDumpslackCommand:
    def _make_args(self, notion_config=None, channel_id="C123"):
        ack = MagicMock()
        respond = MagicMock()
        client = MagicMock()
        body = {"channel_id": channel_id}
        command = {"command": "/ft"}
        return ack, body, command, client, respond, notion_config

    def test_responds_when_notion_not_configured(self):
        ack, body, command, client, respond, _ = self._make_args()
        with patch("firetower.slack_app.handlers.dumpslack.settings") as mock_settings:
            mock_settings.NOTION = None
            handle_dumpslack_command(ack, body, command, client, respond)

        ack.assert_called_once()
        respond.assert_called_once()
        assert "not configured" in respond.call_args[0][0]

    def test_responds_when_no_channel_id(self):
        ack, body, command, client, respond, _ = self._make_args(channel_id="")
        with patch("firetower.slack_app.handlers.dumpslack.settings") as mock_settings:
            mock_settings.NOTION = {"INTEGRATION_TOKEN": "key", "DATABASE_ID": "db"}
            handle_dumpslack_command(ack, body, command, client, respond)

        ack.assert_called_once()
        assert "channel" in respond.call_args[0][0].lower()

    def test_responds_when_no_incident_found(self):
        ack, body, command, client, respond, _ = self._make_args()
        with (
            patch("firetower.slack_app.handlers.dumpslack.settings") as mock_settings,
            patch(
                "firetower.slack_app.handlers.dumpslack.get_incident_from_channel",
                return_value=None,
            ),
        ):
            mock_settings.NOTION = {"INTEGRATION_TOKEN": "key", "DATABASE_ID": "db"}
            handle_dumpslack_command(ack, body, command, client, respond)

        ack.assert_called_once()
        assert "No incident" in respond.call_args[0][0]
