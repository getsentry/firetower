from unittest.mock import MagicMock, patch

from slack_sdk.errors import SlackApiError

from firetower.slack_app.handlers.dumpslack import (
    _build_user_email_cache,
    _download_image,
    _extract_image_urls,
    _extract_notion_page_id,
    _get_channel_messages,
    _get_thread_replies,
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

    def test_handles_trailing_slash(self):
        url = "https://www.notion.so/sentry/Title-abc123def456abc123def456abc123de/"
        result = _extract_notion_page_id(url)
        assert result == "abc123de-f456-abc1-23de-f456abc123de"


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


class TestBuildUserEmailCache:
    def _member(self, uid, email, deleted=False, is_bot=False):
        return {
            "id": uid,
            "deleted": deleted,
            "is_bot": is_bot,
            "profile": {"email": email},
        }

    def test_returns_uid_to_email_map(self):
        mock_client = MagicMock()
        mock_client.users_list.return_value = {
            "ok": True,
            "has_more": False,
            "members": [self._member("U1", "a@sentry.io")],
            "response_metadata": {"next_cursor": ""},
        }

        cache = _build_user_email_cache(mock_client)

        assert cache == {"U1": "a@sentry.io"}

    def test_paginates_using_has_more_and_cursor(self):
        mock_client = MagicMock()
        mock_client.users_list.side_effect = [
            {
                "ok": True,
                "has_more": True,
                "members": [self._member("U1", "a@sentry.io")],
                "response_metadata": {"next_cursor": "cur1"},
            },
            {
                "ok": True,
                "has_more": False,
                "members": [self._member("U2", "b@sentry.io")],
                "response_metadata": {"next_cursor": ""},
            },
        ]

        cache = _build_user_email_cache(mock_client)

        assert len(cache) == 2
        assert mock_client.users_list.call_count == 2
        mock_client.users_list.assert_any_call(limit=200, cursor="cur1")

    def test_stops_when_has_more_false_even_if_cursor_present(self):
        mock_client = MagicMock()
        mock_client.users_list.return_value = {
            "ok": True,
            "has_more": False,
            "members": [self._member("U1", "a@sentry.io")],
            "response_metadata": {"next_cursor": "stale-cursor"},
        }

        _build_user_email_cache(mock_client)

        assert mock_client.users_list.call_count == 1

    def test_skips_bots_and_deleted_members(self):
        mock_client = MagicMock()
        mock_client.users_list.return_value = {
            "ok": True,
            "has_more": False,
            "members": [
                self._member("U1", "human@sentry.io"),
                self._member("U2", "bot@sentry.io", is_bot=True),
                self._member("U3", "gone@sentry.io", deleted=True),
            ],
            "response_metadata": {"next_cursor": ""},
        }

        cache = _build_user_email_cache(mock_client)

        assert cache == {"U1": "human@sentry.io"}

    def test_returns_empty_on_api_error(self):
        mock_client = MagicMock()
        mock_client.users_list.side_effect = Exception("timeout")

        cache = _build_user_email_cache(mock_client)

        assert cache == {}


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
            "has_more": False,
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
            "response_metadata": {"next_cursor": ""},
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

    def test_paginates_conversations_history(self):
        mock_client = MagicMock()
        mock_client.conversations_history.side_effect = [
            {
                "ok": True,
                "has_more": True,
                "messages": [
                    {
                        "type": "message",
                        "user": "U1",
                        "text": "page1",
                        "ts": "1000000002.0",
                    },
                ],
                "response_metadata": {"next_cursor": "cursor1"},
            },
            {
                "ok": True,
                "has_more": False,
                "messages": [
                    {
                        "type": "message",
                        "user": "U1",
                        "text": "page2",
                        "ts": "1000000001.0",
                    },
                ],
                "response_metadata": {"next_cursor": ""},
            },
        ]
        mock_client.users_list.return_value = _make_users_list_response()

        messages = _get_channel_messages(mock_client, "C123")

        assert len(messages) == 2
        assert mock_client.conversations_history.call_count == 2
        mock_client.conversations_history.assert_any_call(
            channel="C123", limit=999, cursor="cursor1"
        )

    def test_includes_image_only_messages(self):
        mock_client = MagicMock()
        mock_client.token = "xoxb-token"
        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "user": "U1",
                    "text": "",
                    "ts": "1000000001.000000",
                    "attachments": [{"image_url": "https://p.datadoghq.com/graph.png"}],
                },
            ],
        }
        mock_client.users_list.return_value = _make_users_list_response()

        with patch(
            "firetower.slack_app.handlers.dumpslack._download_image", return_value=None
        ):
            messages = _get_channel_messages(mock_client, "C123")

        assert len(messages) == 1

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

    def test_preserves_partial_results_when_pagination_fails_mid_way(self):
        mock_client = MagicMock()
        mock_client.conversations_history.side_effect = [
            {
                "ok": True,
                "has_more": True,
                "messages": [
                    {
                        "type": "message",
                        "user": "U1",
                        "text": "page1",
                        "ts": "1000000001.0",
                    },
                ],
                "response_metadata": {"next_cursor": "cur1"},
            },
            Exception("network error"),
        ]
        mock_client.users_list.return_value = _make_users_list_response()

        messages = _get_channel_messages(mock_client, "C123")

        # First page was fetched before the error; should not be discarded
        assert len(messages) == 1
        assert messages[0]["text"] == "page1"


class TestGetThreadReplies:
    def test_returns_replies_excluding_parent(self):
        mock_client = MagicMock()
        mock_client.conversations_replies.return_value = {
            "ok": True,
            "has_more": False,
            "messages": [
                {"type": "message", "user": "U1", "text": "parent", "ts": "1.0"},
                {"type": "message", "user": "U2", "text": "reply1", "ts": "2.0"},
            ],
            "response_metadata": {"next_cursor": ""},
        }

        replies = _get_thread_replies(mock_client, "C123", "1.0")

        assert len(replies) == 1
        assert replies[0]["text"] == "reply1"

    def test_paginates_via_next_cursor(self):
        mock_client = MagicMock()
        mock_client.conversations_replies.side_effect = [
            {
                "ok": True,
                "has_more": True,
                "messages": [
                    {"type": "message", "user": "U1", "text": "parent", "ts": "1.0"},
                    {"type": "message", "user": "U2", "text": "r1", "ts": "2.0"},
                ],
                "response_metadata": {"next_cursor": "cur1"},
            },
            {
                "ok": True,
                "has_more": False,
                "messages": [
                    {"type": "message", "user": "U3", "text": "r2", "ts": "3.0"},
                ],
                "response_metadata": {"next_cursor": ""},
            },
        ]

        replies = _get_thread_replies(mock_client, "C123", "1.0")

        assert len(replies) == 2
        assert mock_client.conversations_replies.call_count == 2
        mock_client.conversations_replies.assert_any_call(
            channel="C123", ts="1.0", limit=999, cursor="cur1"
        )

    def test_passes_limit_999_on_first_call(self):
        mock_client = MagicMock()
        mock_client.conversations_replies.return_value = {
            "ok": True,
            "has_more": False,
            "messages": [],
            "response_metadata": {"next_cursor": ""},
        }

        _get_thread_replies(mock_client, "C123", "1.0")

        mock_client.conversations_replies.assert_called_once_with(
            channel="C123", ts="1.0", limit=999
        )

    def test_skips_bot_replies(self):
        mock_client = MagicMock()
        mock_client.conversations_replies.return_value = {
            "ok": True,
            "has_more": False,
            "messages": [
                {"type": "message", "user": "U1", "text": "parent", "ts": "1.0"},
                {
                    "type": "message",
                    "user": "B1",
                    "bot_id": "B1",
                    "text": "bot reply",
                    "ts": "2.0",
                },
                {"type": "message", "user": "U2", "text": "human reply", "ts": "3.0"},
            ],
            "response_metadata": {"next_cursor": ""},
        }

        replies = _get_thread_replies(mock_client, "C123", "1.0")

        assert len(replies) == 1
        assert replies[0]["text"] == "human reply"

    def test_skips_replies_without_user(self):
        mock_client = MagicMock()
        mock_client.conversations_replies.return_value = {
            "ok": True,
            "has_more": False,
            "messages": [
                {"type": "message", "user": "U1", "text": "parent", "ts": "1.0"},
                {"type": "message", "text": "no user", "ts": "2.0"},
                {"type": "message", "user": "U2", "text": "has user", "ts": "3.0"},
            ],
            "response_metadata": {"next_cursor": ""},
        }

        replies = _get_thread_replies(mock_client, "C123", "1.0")

        assert len(replies) == 1
        assert replies[0]["text"] == "has user"

    def test_returns_empty_on_api_error(self):
        mock_client = MagicMock()
        mock_client.conversations_replies.side_effect = Exception("timeout")

        replies = _get_thread_replies(mock_client, "C123", "1.0")

        assert replies == []


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
        assert result == [
            {"image_url": "https://p.datadoghq.com/img/graph.png", "source_url": ""}
        ]

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
        msg = {
            "files": [
                {
                    "mimetype": "application/pdf",
                    "url_private": "https://files.slack.com/doc.pdf",
                }
            ]
        }
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

        with patch(
            "firetower.slack_app.handlers.dumpslack.httpx.get",
            return_value=mock_response,
        ) as mock_get:
            result = _download_image(
                "https://p.datadoghq.com/img/graph.png", "xoxb-token"
            )

        assert result == (b"PNG_DATA", "image/png")
        call_headers = mock_get.call_args.kwargs["headers"]
        assert "Authorization" not in call_headers

    def test_adds_slack_bearer_token_for_slack_urls(self):
        mock_response = MagicMock()
        mock_response.content = b"IMG"
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.raise_for_status = MagicMock()

        with patch(
            "firetower.slack_app.handlers.dumpslack.httpx.get",
            return_value=mock_response,
        ) as mock_get:
            _download_image(
                "https://files.slack.com/files-pri/T1/img.jpg", "xoxb-token"
            )

        call_headers = mock_get.call_args.kwargs["headers"]
        assert call_headers["Authorization"] == "Bearer xoxb-token"

    def test_returns_none_on_request_failure(self):
        with patch(
            "firetower.slack_app.handlers.dumpslack.httpx.get",
            side_effect=Exception("timeout"),
        ):
            result = _download_image("https://example.com/img.png", "token")

        assert result is None

    def test_returns_none_for_non_image_content_type(self):
        mock_response = MagicMock()
        mock_response.content = b"<html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()

        with patch(
            "firetower.slack_app.handlers.dumpslack.httpx.get",
            return_value=mock_response,
        ):
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

    def test_chat_post_message_failure_does_not_raise(self):
        ack, body, command, client, respond, _ = self._make_args()
        client.chat_postMessage.side_effect = SlackApiError(
            message="not_in_channel", response={"ok": False, "error": "not_in_channel"}
        )
        mock_incident = MagicMock()
        mock_incident.external_links.filter.return_value.first.return_value = None
        mock_incident.captain = None
        mock_page = {"id": "page-id", "url": "https://notion.so/page-id"}
        with (
            patch("firetower.slack_app.handlers.dumpslack.settings") as mock_settings,
            patch(
                "firetower.slack_app.handlers.dumpslack.get_incident_from_channel",
                return_value=mock_incident,
            ),
            patch(
                "firetower.slack_app.handlers.dumpslack.NotionService"
            ) as mock_notion_cls,
            patch(
                "firetower.slack_app.handlers.dumpslack._get_channel_messages",
                return_value=[],
            ),
            patch("firetower.slack_app.handlers.dumpslack.ExternalLink"),
        ):
            mock_settings.NOTION = {"INTEGRATION_TOKEN": "key", "DATABASE_ID": "db"}
            mock_settings.FIRETOWER_BASE_URL = "https://firetower.example.com"
            mock_notion_cls.return_value.create_postmortem_page.return_value = mock_page
            mock_notion_cls.return_value.apply_template.return_value = None
            handle_dumpslack_command(ack, body, command, client, respond)

        # SlackApiError on chat_postMessage must not propagate
        client.chat_postMessage.assert_called_once()
        ack.assert_called_once()
