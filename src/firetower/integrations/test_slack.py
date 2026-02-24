"""
Basic pytest tests for Slack integration service.
"""

import os
from unittest.mock import MagicMock, patch

from slack_sdk.errors import SlackApiError

from .services.slack import SlackService

# Set up Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "firetower.settings")

import django
from django.conf import settings

# Setup Django
django.setup()


class TestSlackService:
    """Test suite for SlackService"""

    def test_initialization_without_bot_token(self):
        """Test that SlackService initializes without bot token but with no client."""
        mock_slack_config = {
            "BOT_TOKEN": None,
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            service = SlackService()

            # Verify the service was created but client is None
            assert service.bot_token is None
            assert service.team_id == "sentry"
            assert service.client is None

    def test_initialization_without_team_id(self):
        """Test that SlackService handles missing team_id gracefully."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": None,
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch("firetower.integrations.services.slack.WebClient"):
                service = SlackService()

                # Verify the service was created but team_id is None
                assert service.bot_token == "xoxb-test-token"
                assert service.team_id is None

    def test_initialization_with_bot_token(self):
        """Test that SlackService initializes successfully with bot token."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                service = SlackService()

                # Verify the service was created and WebClient was initialized
                assert service.bot_token == "xoxb-test-token"
                assert service.team_id == "sentry"
                assert service.client is not None
                mock_client.assert_called_once_with(token="xoxb-test-token")

    def test_get_user_profile_by_email_success(self):
        """Test successful user profile fetch from Slack."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch("firetower.integrations.services.slack.WebClient") as MockClient:
                mock_client = MagicMock()
                MockClient.return_value = mock_client

                mock_client.users_lookupByEmail.return_value = {
                    "user": {
                        "id": "U12345",
                        "real_name": "John Doe",
                        "profile": {
                            "display_name": "Johnny",
                            "image_512": "https://example.com/avatar-512.jpg",
                        },
                    }
                }

                service = SlackService()
                profile = service.get_user_profile_by_email("john@example.com")

                assert profile is not None
                assert profile["slack_user_id"] == "U12345"
                assert profile["name"] == "Johnny"
                assert profile["first_name"] == "John"
                assert profile["last_name"] == "Doe"
                assert profile["avatar_url"] == "https://example.com/avatar-512.jpg"

    def test_get_user_profile_by_email_not_found(self):
        """Test user profile fetch when user doesn't exist in Slack."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch("firetower.integrations.services.slack.WebClient") as MockClient:
                mock_client = MagicMock()
                MockClient.return_value = mock_client

                mock_response = MagicMock()
                mock_response.get.return_value = "users_not_found"
                mock_client.users_lookupByEmail.side_effect = SlackApiError(
                    "user_not_found", mock_response
                )

                service = SlackService()
                profile = service.get_user_profile_by_email("nonexistent@example.com")

                assert profile is None

    def test_get_user_profile_without_client(self):
        """Test that profile fetch returns None when Slack client not initialized."""
        mock_slack_config = {
            "BOT_TOKEN": None,
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            service = SlackService()
            profile = service.get_user_profile_by_email("test@example.com")

            assert profile is None

    def _make_service(self):
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }
        with patch.object(settings, "SLACK", mock_slack_config):
            with patch("firetower.integrations.services.slack.WebClient") as MockClient:
                mock_client = MagicMock()
                MockClient.return_value = mock_client
                service = SlackService()
        return service, mock_client

    def test_create_channel_success(self):
        service, mock_client = self._make_service()
        mock_client.conversations_create.return_value = {"channel": {"id": "C12345"}}
        result = service.create_channel("inc-2014")
        assert result == "C12345"
        mock_client.conversations_create.assert_called_once_with(name="inc-2014")

    def test_create_channel_no_client(self):
        mock_slack_config = {"BOT_TOKEN": None, "TEAM_ID": "sentry"}
        with patch.object(settings, "SLACK", mock_slack_config):
            service = SlackService()
        assert service.create_channel("inc-2014") is None

    def test_create_channel_api_error(self):
        service, mock_client = self._make_service()
        mock_response = MagicMock()
        mock_response.get.return_value = "name_taken"
        mock_client.conversations_create.side_effect = SlackApiError(
            "name_taken", mock_response
        )
        assert service.create_channel("inc-2014") is None

    def test_set_channel_topic_success(self):
        service, mock_client = self._make_service()
        assert service.set_channel_topic("C12345", "test topic") is True
        mock_client.conversations_setTopic.assert_called_once_with(
            channel="C12345", topic="test topic"
        )

    def test_set_channel_topic_no_client(self):
        mock_slack_config = {"BOT_TOKEN": None, "TEAM_ID": "sentry"}
        with patch.object(settings, "SLACK", mock_slack_config):
            service = SlackService()
        assert service.set_channel_topic("C12345", "topic") is False

    def test_set_channel_topic_api_error(self):
        service, mock_client = self._make_service()
        mock_response = MagicMock()
        mock_client.conversations_setTopic.side_effect = SlackApiError(
            "error", mock_response
        )
        assert service.set_channel_topic("C12345", "topic") is False

    def test_invite_to_channel_success(self):
        service, mock_client = self._make_service()
        assert service.invite_to_channel("C12345", ["U111", "U222"]) is True
        mock_client.conversations_invite.assert_called_once_with(
            channel="C12345", users="U111,U222"
        )

    def test_invite_to_channel_no_client(self):
        mock_slack_config = {"BOT_TOKEN": None, "TEAM_ID": "sentry"}
        with patch.object(settings, "SLACK", mock_slack_config):
            service = SlackService()
        assert service.invite_to_channel("C12345", ["U111"]) is False

    def test_invite_to_channel_api_error(self):
        service, mock_client = self._make_service()
        mock_response = MagicMock()
        mock_client.conversations_invite.side_effect = SlackApiError(
            "error", mock_response
        )
        assert service.invite_to_channel("C12345", ["U111"]) is False

    def test_post_message_success(self):
        service, mock_client = self._make_service()
        assert service.post_message("C12345", "hello") is True
        mock_client.chat_postMessage.assert_called_once_with(
            channel="C12345", text="hello", blocks=None
        )

    def test_post_message_with_blocks(self):
        service, mock_client = self._make_service()
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "hi"}}]
        assert service.post_message("C12345", "hello", blocks=blocks) is True
        mock_client.chat_postMessage.assert_called_once_with(
            channel="C12345", text="hello", blocks=blocks
        )

    def test_post_message_no_client(self):
        mock_slack_config = {"BOT_TOKEN": None, "TEAM_ID": "sentry"}
        with patch.object(settings, "SLACK", mock_slack_config):
            service = SlackService()
        assert service.post_message("C12345", "hello") is False

    def test_post_message_api_error(self):
        service, mock_client = self._make_service()
        mock_response = MagicMock()
        mock_client.chat_postMessage.side_effect = SlackApiError("error", mock_response)
        assert service.post_message("C12345", "hello") is False

    def test_add_bookmark_success(self):
        service, mock_client = self._make_service()
        assert (
            service.add_bookmark("C12345", "Firetower", "https://example.com") is True
        )
        mock_client.bookmarks_add.assert_called_once_with(
            channel_id="C12345",
            title="Firetower",
            type="link",
            link="https://example.com",
        )

    def test_add_bookmark_no_client(self):
        mock_slack_config = {"BOT_TOKEN": None, "TEAM_ID": "sentry"}
        with patch.object(settings, "SLACK", mock_slack_config):
            service = SlackService()
        assert service.add_bookmark("C12345", "title", "https://example.com") is False

    def test_add_bookmark_api_error(self):
        service, mock_client = self._make_service()
        mock_response = MagicMock()
        mock_client.bookmarks_add.side_effect = SlackApiError("error", mock_response)
        assert service.add_bookmark("C12345", "title", "https://example.com") is False

    def test_get_channel_history_success(self):
        service, mock_client = self._make_service()
        mock_client.conversations_history.return_value = {
            "messages": [{"text": "hello"}, {"text": "world"}]
        }
        result = service.get_channel_history("C12345")
        assert result == [{"text": "hello"}, {"text": "world"}]
        mock_client.conversations_history.assert_called_once_with(
            channel="C12345", limit=1000
        )

    def test_get_channel_history_custom_limit(self):
        service, mock_client = self._make_service()
        mock_client.conversations_history.return_value = {"messages": []}
        service.get_channel_history("C12345", limit=10)
        mock_client.conversations_history.assert_called_once_with(
            channel="C12345", limit=10
        )

    def test_get_channel_history_no_client(self):
        mock_slack_config = {"BOT_TOKEN": None, "TEAM_ID": "sentry"}
        with patch.object(settings, "SLACK", mock_slack_config):
            service = SlackService()
        assert service.get_channel_history("C12345") is None

    def test_get_channel_history_api_error(self):
        service, mock_client = self._make_service()
        mock_response = MagicMock()
        mock_client.conversations_history.side_effect = SlackApiError(
            "error", mock_response
        )
        assert service.get_channel_history("C12345") is None

    def test_build_channel_url(self):
        service, _ = self._make_service()
        url = service.build_channel_url("C12345")
        assert url == "https://slack.com/archives/C12345"
        assert service.parse_channel_id_from_url(url) == "C12345"
