"""
Basic pytest tests for Slack integration service.
"""

import os
from unittest.mock import MagicMock, patch

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

                # Should return None when trying to get a URL without team_id
                url = service.get_channel_url_by_name("test-channel")
                assert url is None

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

    def test_get_channel_id_by_name_without_client(self):
        """Test that _get_channel_id_by_name returns None when client is not initialized."""
        mock_slack_config = {
            "BOT_TOKEN": None,
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            service = SlackService()
            channel_id = service._get_channel_id_by_name("test-channel")

            assert channel_id is None

    def test_get_channel_id_by_name_success(self):
        """Test successful channel ID lookup by name."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the conversations_list response
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance
                mock_client_instance.conversations_list.return_value = {
                    "channels": [
                        {"id": "C123456", "name": "test-channel"},
                        {"id": "C789012", "name": "other-channel"},
                    ]
                }

                service = SlackService()
                channel_id = service._get_channel_id_by_name("test-channel")

                assert channel_id == "C123456"
                mock_client_instance.conversations_list.assert_called_once_with(
                    types="private_channel,public_channel"
                )

    def test_get_channel_id_by_name_not_found(self):
        """Test channel ID lookup when channel doesn't exist."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the conversations_list response
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance
                mock_client_instance.conversations_list.return_value = {
                    "channels": [
                        {"id": "C123456", "name": "test-channel"},
                    ]
                }

                service = SlackService()
                channel_id = service._get_channel_id_by_name("nonexistent-channel")

                assert channel_id is None

    def test_get_channel_id_by_name_api_error(self):
        """Test channel ID lookup when Slack API returns an error."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the conversations_list to raise SlackApiError
                from slack_sdk.errors import SlackApiError

                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance
                mock_client_instance.conversations_list.side_effect = SlackApiError(
                    message="API error", response={"error": "invalid_auth"}
                )

                service = SlackService()
                channel_id = service._get_channel_id_by_name("test-channel")

                # Should return None on error
                assert channel_id is None

    def test_build_channel_url(self):
        """Test building Slack channel URL from channel ID."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch("firetower.integrations.services.slack.WebClient"):
                service = SlackService()
                url = service._build_channel_url("C123456")

                assert url == "https://sentry.slack.com/archives/C123456"

    def test_build_channel_url_custom_team(self):
        """Test building Slack channel URL with custom team ID."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "mycompany",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch("firetower.integrations.services.slack.WebClient"):
                service = SlackService()
                url = service._build_channel_url("C123456")

                assert url == "https://mycompany.slack.com/archives/C123456"

    def test_get_channel_url_by_name_success(self):
        """Test getting full channel URL by name."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the conversations_list response
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance
                mock_client_instance.conversations_list.return_value = {
                    "channels": [
                        {"id": "C123456", "name": "inc-123"},
                    ]
                }

                service = SlackService()
                url = service.get_channel_url_by_name("inc-123")

                assert url == "https://sentry.slack.com/archives/C123456"

    def test_get_channel_url_by_name_not_found(self):
        """Test getting channel URL when channel doesn't exist."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the conversations_list response
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance
                mock_client_instance.conversations_list.return_value = {
                    "channels": [
                        {"id": "C123456", "name": "inc-123"},
                    ]
                }

                service = SlackService()
                url = service.get_channel_url_by_name("nonexistent-channel")

                assert url is None

    def test_get_channel_members_without_client(self):
        """Test that get_channel_members returns None when client is not initialized."""
        mock_slack_config = {
            "BOT_TOKEN": None,
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            service = SlackService()
            members = service.get_channel_members("C123456")

            assert members is None

    def test_get_channel_members_success(self):
        """Test successful channel members lookup."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the conversations_members response
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance
                mock_client_instance.conversations_members.return_value = {
                    "members": ["U123456", "U789012", "U345678"]
                }

                service = SlackService()
                members = service.get_channel_members("C123456")

                assert members == ["U123456", "U789012", "U345678"]
                mock_client_instance.conversations_members.assert_called_once_with(
                    channel="C123456"
                )

    def test_get_channel_members_api_error(self):
        """Test channel members lookup when Slack API returns an error."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the conversations_members to raise SlackApiError
                from slack_sdk.errors import SlackApiError

                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance
                mock_client_instance.conversations_members.side_effect = SlackApiError(
                    message="API error", response={"error": "channel_not_found"}
                )

                service = SlackService()
                members = service.get_channel_members("C123456")

                # Should return None on error
                assert members is None

    def test_get_user_info_without_client(self):
        """Test that get_user_info returns None when client is not initialized."""
        mock_slack_config = {
            "BOT_TOKEN": None,
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            service = SlackService()
            user_info = service.get_user_info("U123456")

            assert user_info is None

    def test_get_user_info_success(self):
        """Test successful user info lookup."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the users_info response
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance
                mock_client_instance.users_info.return_value = {
                    "user": {
                        "id": "U123456",
                        "name": "john.smith",
                        "profile": {
                            "real_name": "John Smith",
                            "display_name": "John",
                            "image_48": "https://avatars.slack-edge.com/U123456_48.jpg",
                            "email": "john.smith@example.com",
                        },
                    }
                }

                service = SlackService()
                user_info = service.get_user_info("U123456")

                assert user_info == {
                    "id": "U123456",
                    "name": "john.smith",
                    "real_name": "John Smith",
                    "display_name": "John",
                    "avatar_url": "https://avatars.slack-edge.com/U123456_48.jpg",
                    "email": "john.smith@example.com",
                }
                mock_client_instance.users_info.assert_called_once_with(user="U123456")

    def test_get_user_info_api_error(self):
        """Test user info lookup when Slack API returns an error."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the users_info to raise SlackApiError
                from slack_sdk.errors import SlackApiError

                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance
                mock_client_instance.users_info.side_effect = SlackApiError(
                    message="API error", response={"error": "user_not_found"}
                )

                service = SlackService()
                user_info = service.get_user_info("U123456")

                # Should return None on error
                assert user_info is None

    def test_get_channel_participants_success(self):
        """Test getting full channel participants with all data."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the full flow
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance

                # Mock conversations_list
                mock_client_instance.conversations_list.return_value = {
                    "channels": [{"id": "C123456", "name": "inc-123"}]
                }

                # Mock conversations_members
                mock_client_instance.conversations_members.return_value = {
                    "members": ["U123456", "U789012"]
                }

                # Mock users_info calls
                def mock_users_info(user):
                    if user == "U123456":
                        return {
                            "user": {
                                "id": "U123456",
                                "name": "john.smith",
                                "profile": {
                                    "real_name": "John Smith",
                                    "display_name": "John",
                                    "image_48": "https://avatars.slack-edge.com/U123456_48.jpg",
                                    "email": "john.smith@example.com",
                                },
                            }
                        }
                    elif user == "U789012":
                        return {
                            "user": {
                                "id": "U789012",
                                "name": "jane.doe",
                                "profile": {
                                    "real_name": "Jane Doe",
                                    "display_name": "Jane",
                                    "image_48": "https://avatars.slack-edge.com/U789012_48.jpg",
                                    "email": "jane.doe@example.com",
                                },
                            }
                        }

                mock_client_instance.users_info.side_effect = mock_users_info

                service = SlackService()
                participants = service.get_channel_participants("inc-123")

                assert len(participants) == 2
                assert participants[0] == {
                    "name": "John Smith",
                    "email": "john.smith@example.com",
                    "avatar_url": "https://avatars.slack-edge.com/U123456_48.jpg",
                    "role": None,
                }
                assert participants[1] == {
                    "name": "Jane Doe",
                    "email": "jane.doe@example.com",
                    "avatar_url": "https://avatars.slack-edge.com/U789012_48.jpg",
                    "role": None,
                }

    def test_get_channel_participants_channel_not_found(self):
        """Test get_channel_participants when channel doesn't exist."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock conversations_list with no matching channel
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance
                mock_client_instance.conversations_list.return_value = {
                    "channels": [{"id": "C123456", "name": "other-channel"}]
                }

                service = SlackService()
                participants = service.get_channel_participants("inc-123")

                assert participants == []

    def test_get_channel_participants_no_members(self):
        """Test get_channel_participants when channel has no members."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the flow
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance

                # Mock conversations_list
                mock_client_instance.conversations_list.return_value = {
                    "channels": [{"id": "C123456", "name": "inc-123"}]
                }

                # Mock conversations_members with empty list
                mock_client_instance.conversations_members.return_value = {
                    "members": []
                }

                service = SlackService()
                participants = service.get_channel_participants("inc-123")

                assert participants == []

    def test_get_channel_participants_mixed_success_failure(self):
        """Test get_channel_participants when some user info calls fail."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the full flow
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance

                # Mock conversations_list
                mock_client_instance.conversations_list.return_value = {
                    "channels": [{"id": "C123456", "name": "inc-123"}]
                }

                # Mock conversations_members
                mock_client_instance.conversations_members.return_value = {
                    "members": ["U123456", "U789012", "U345678"]
                }

                # Mock users_info calls - one succeeds, one fails, one succeeds
                call_count = [0]

                def mock_users_info(user):
                    call_count[0] += 1
                    if user == "U123456":
                        return {
                            "user": {
                                "id": "U123456",
                                "name": "john.smith",
                                "profile": {
                                    "real_name": "John Smith",
                                    "display_name": "John",
                                    "image_48": "https://avatars.slack-edge.com/U123456_48.jpg",
                                    "email": "john.smith@example.com",
                                },
                            }
                        }
                    elif user == "U789012":
                        from slack_sdk.errors import SlackApiError

                        raise SlackApiError(
                            message="API error", response={"error": "user_not_found"}
                        )
                    elif user == "U345678":
                        return {
                            "user": {
                                "id": "U345678",
                                "name": "alice.brown",
                                "profile": {
                                    "real_name": "Alice Brown",
                                    "display_name": "Alice",
                                    "image_48": "https://avatars.slack-edge.com/U345678_48.jpg",
                                    "email": "alice.brown@example.com",
                                },
                            }
                        }

                mock_client_instance.users_info.side_effect = mock_users_info

                service = SlackService()
                participants = service.get_channel_participants("inc-123")

                # Should only include the successful user info fetches
                assert len(participants) == 2
                assert participants[0]["name"] == "John Smith"
                assert participants[0]["email"] == "john.smith@example.com"
                assert participants[1]["name"] == "Alice Brown"
                assert participants[1]["email"] == "alice.brown@example.com"

    def test_get_channel_participants_empty_display_name(self):
        """Test get_channel_participants when user has no display_name."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the full flow
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance

                # Mock conversations_list
                mock_client_instance.conversations_list.return_value = {
                    "channels": [{"id": "C123456", "name": "inc-123"}]
                }

                # Mock conversations_members
                mock_client_instance.conversations_members.return_value = {
                    "members": ["U123456"]
                }

                # Mock users_info with empty display_name
                mock_client_instance.users_info.return_value = {
                    "user": {
                        "id": "U123456",
                        "name": "john.smith",
                        "profile": {
                            "real_name": "John Smith",
                            "display_name": "",  # Empty display_name
                            "image_48": "https://avatars.slack-edge.com/U123456_48.jpg",
                            "email": "john.smith@example.com",
                        },
                    }
                }

                service = SlackService()
                participants = service.get_channel_participants("inc-123")

                # Should use real_name
                assert len(participants) == 1
                assert participants[0] == {
                    "name": "John Smith",  # Uses real_name
                    "email": "john.smith@example.com",
                    "avatar_url": "https://avatars.slack-edge.com/U123456_48.jpg",
                    "role": None,
                }

    def test_get_channel_participants_no_real_name(self):
        """Test get_channel_participants when user has no real_name set."""
        mock_slack_config = {
            "BOT_TOKEN": "xoxb-test-token",
            "TEAM_ID": "sentry",
        }

        with patch.object(settings, "SLACK", mock_slack_config):
            with patch(
                "firetower.integrations.services.slack.WebClient"
            ) as mock_client:
                # Mock the full flow
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance

                # Mock conversations_list
                mock_client_instance.conversations_list.return_value = {
                    "channels": [{"id": "C123456", "name": "inc-123"}]
                }

                # Mock conversations_members
                mock_client_instance.conversations_members.return_value = {
                    "members": ["U123456"]
                }

                # Mock users_info with no real_name
                mock_client_instance.users_info.return_value = {
                    "user": {
                        "id": "U123456",
                        "name": "spencer.murray",
                        "profile": {
                            "real_name": "",  # Empty real_name
                            "display_name": "spencer",
                            "image_48": "https://avatars.slack-edge.com/U123456_48.jpg",
                            "email": "spencer.murray@example.com",
                        },
                    }
                }

                service = SlackService()
                participants = service.get_channel_participants("inc-123")

                # Should use username as-is when no real_name
                assert len(participants) == 1
                assert participants[0] == {
                    "name": "spencer.murray",  # Username as-is
                    "email": "spencer.murray@example.com",
                    "avatar_url": "https://avatars.slack-edge.com/U123456_48.jpg",
                    "role": None,
                }
