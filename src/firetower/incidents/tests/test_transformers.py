"""
Tests for incident transformers.
"""

import os
from unittest.mock import MagicMock, patch

from firetower.incidents.transformers import extract_participants

# Set up Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "firetower.settings")

import django

# Setup Django
django.setup()


class TestExtractParticipants:
    """Test suite for extract_participants function"""

    def test_extract_participants_from_slack_with_roles(self):
        """Test extracting participants from Slack with Captain and Reporter roles matched by email."""
        jira_incident = {
            "id": "INC-123",
            "assignee": "John Smith",
            "assignee_email": "john.smith@example.com",
            "reporter": "Jane Doe",
            "reporter_email": "jane.doe@example.com",
        }

        # Mock SlackService
        with patch(
            "firetower.incidents.transformers.SlackService"
        ) as mock_slack_service:
            mock_service_instance = MagicMock()
            mock_slack_service.return_value = mock_service_instance

            # Mock Slack participants including the assignee and reporter
            mock_service_instance.get_channel_participants.return_value = [
                {
                    "name": "John Smith",
                    "email": "john.smith@example.com",
                    "avatar_url": "https://avatars.slack-edge.com/U123456_48.jpg",
                    "role": None,
                },
                {
                    "name": "Jane Doe",
                    "email": "jane.doe@example.com",
                    "avatar_url": "https://avatars.slack-edge.com/U789012_48.jpg",
                    "role": None,
                },
                {
                    "name": "Alice Brown",
                    "email": "alice.brown@example.com",
                    "avatar_url": "https://avatars.slack-edge.com/U345678_48.jpg",
                    "role": None,
                },
            ]

            participants = extract_participants(jira_incident)

            # Verify all participants are present
            assert len(participants) == 3

            # Verify Captain role is assigned by email match
            captain = next(
                (p for p in participants if p.get("email") == "john.smith@example.com"),
                None,
            )
            assert captain is not None
            assert captain["role"] == "Captain"
            assert captain["name"] == "John Smith"

            # Verify Reporter role is assigned by email match
            reporter = next(
                (p for p in participants if p.get("email") == "jane.doe@example.com"),
                None,
            )
            assert reporter is not None
            assert reporter["role"] == "Reporter"
            assert reporter["name"] == "Jane Doe"

            # Verify other participant has no role
            other = next(
                (
                    p
                    for p in participants
                    if p.get("email") == "alice.brown@example.com"
                ),
                None,
            )
            assert other is not None
            assert other["role"] is None

    def test_extract_participants_slack_fetch_fails(self):
        """Test fallback to Jira-only participants when Slack fetch fails."""
        jira_incident = {
            "id": "INC-123",
            "assignee": "John Smith",
            "assignee_email": "john.smith@example.com",
            "reporter": "Jane Doe",
            "reporter_email": "jane.doe@example.com",
        }

        # Mock SlackService to return empty list (failure)
        with patch(
            "firetower.incidents.transformers.SlackService"
        ) as mock_slack_service:
            mock_service_instance = MagicMock()
            mock_slack_service.return_value = mock_service_instance
            mock_service_instance.get_channel_participants.return_value = []

            participants = extract_participants(jira_incident)

            # Should fall back to Jira-only data
            assert len(participants) == 2

            # Verify Captain from Jira
            captain = next((p for p in participants if p["role"] == "Captain"), None)
            assert captain is not None
            assert captain["name"] == "John Smith"
            assert captain["email"] == "john.smith@example.com"
            assert captain["avatar_url"] is None

            # Verify Reporter from Jira
            reporter = next((p for p in participants if p["role"] == "Reporter"), None)
            assert reporter is not None
            assert reporter["name"] == "Jane Doe"
            assert reporter["email"] == "jane.doe@example.com"
            assert reporter["avatar_url"] is None

    def test_extract_participants_assignee_not_in_channel(self):
        """Test when assignee is not in the Slack channel (email not matched)."""
        jira_incident = {
            "id": "INC-123",
            "assignee": "John Smith",
            "assignee_email": "john.smith@example.com",
            "reporter": None,
            "reporter_email": None,
        }

        # Mock SlackService with participants that don't include assignee
        with patch(
            "firetower.incidents.transformers.SlackService"
        ) as mock_slack_service:
            mock_service_instance = MagicMock()
            mock_slack_service.return_value = mock_service_instance

            mock_service_instance.get_channel_participants.return_value = [
                {
                    "name": "Alice Brown",
                    "email": "alice.brown@example.com",
                    "avatar_url": "https://avatars.slack-edge.com/U345678_48.jpg",
                    "role": None,
                },
                {
                    "name": "Bob Wilson",
                    "email": "bob.wilson@example.com",
                    "avatar_url": "https://avatars.slack-edge.com/U456789_48.jpg",
                    "role": None,
                },
            ]

            participants = extract_participants(jira_incident)

            # Should include Slack participants + assignee from Jira
            assert len(participants) == 3

            # Verify Captain is added from Jira
            captain = next((p for p in participants if p["role"] == "Captain"), None)
            assert captain is not None
            assert captain["name"] == "John Smith"
            assert captain["email"] == "john.smith@example.com"
            assert captain["avatar_url"] is None

            # Verify Slack participants are included
            alice = next(
                (
                    p
                    for p in participants
                    if p.get("email") == "alice.brown@example.com"
                ),
                None,
            )
            assert alice is not None
            assert alice["role"] is None

    def test_extract_participants_reporter_not_in_channel(self):
        """Test when reporter is not in the Slack channel (email not matched)."""
        jira_incident = {
            "id": "INC-123",
            "assignee": "John Smith",
            "assignee_email": "john.smith@example.com",
            "reporter": "Jane Doe",
            "reporter_email": "jane.doe@example.com",
        }

        # Mock SlackService with participants that include assignee but not reporter
        with patch(
            "firetower.incidents.transformers.SlackService"
        ) as mock_slack_service:
            mock_service_instance = MagicMock()
            mock_slack_service.return_value = mock_service_instance

            mock_service_instance.get_channel_participants.return_value = [
                {
                    "name": "John Smith",
                    "email": "john.smith@example.com",
                    "avatar_url": "https://avatars.slack-edge.com/U123456_48.jpg",
                    "role": None,
                },
                {
                    "name": "Alice Brown",
                    "email": "alice.brown@example.com",
                    "avatar_url": "https://avatars.slack-edge.com/U345678_48.jpg",
                    "role": None,
                },
            ]

            participants = extract_participants(jira_incident)

            # Should include Slack participants + reporter from Jira
            assert len(participants) == 3

            # Verify Captain role is assigned to John in channel (matched by email)
            captain = next((p for p in participants if p["role"] == "Captain"), None)
            assert captain is not None
            assert captain["name"] == "John Smith"
            assert captain["email"] == "john.smith@example.com"
            assert (
                captain["avatar_url"] == "https://avatars.slack-edge.com/U123456_48.jpg"
            )

            # Verify Reporter is added from Jira
            reporter = next((p for p in participants if p["role"] == "Reporter"), None)
            assert reporter is not None
            assert reporter["name"] == "Jane Doe"
            assert reporter["email"] == "jane.doe@example.com"
            assert reporter["avatar_url"] is None

    def test_extract_participants_no_jira_assignee(self):
        """Test when Jira has no assignee."""
        jira_incident = {
            "id": "INC-123",
            "assignee": None,
            "assignee_email": None,
            "reporter": None,
            "reporter_email": None,
        }

        # Mock SlackService
        with patch(
            "firetower.incidents.transformers.SlackService"
        ) as mock_slack_service:
            mock_service_instance = MagicMock()
            mock_slack_service.return_value = mock_service_instance

            mock_service_instance.get_channel_participants.return_value = [
                {
                    "name": "Alice Brown",
                    "email": "alice.brown@example.com",
                    "avatar_url": "https://avatars.slack-edge.com/U345678_48.jpg",
                    "role": None,
                },
            ]

            participants = extract_participants(jira_incident)

            # Should only include Slack participants
            assert len(participants) == 1
            assert participants[0]["name"] == "Alice Brown"
            assert participants[0]["role"] is None

    def test_extract_participants_assignee_is_reporter(self):
        """Test when assignee and reporter are the same person (same email)."""
        jira_incident = {
            "id": "INC-123",
            "assignee": "John Smith",
            "assignee_email": "john.smith@example.com",
            "reporter": "John Smith",
            "reporter_email": "john.smith@example.com",
        }

        # Mock SlackService
        with patch(
            "firetower.incidents.transformers.SlackService"
        ) as mock_slack_service:
            mock_service_instance = MagicMock()
            mock_slack_service.return_value = mock_service_instance

            mock_service_instance.get_channel_participants.return_value = [
                {
                    "name": "John Smith",
                    "email": "john.smith@example.com",
                    "avatar_url": "https://avatars.slack-edge.com/U123456_48.jpg",
                    "role": None,
                },
            ]

            participants = extract_participants(jira_incident)

            # Should only have one participant with Captain role (not Reporter)
            assert len(participants) == 1
            assert participants[0]["name"] == "John Smith"
            assert participants[0]["role"] == "Captain"
            assert participants[0]["email"] == "john.smith@example.com"

    def test_extract_participants_no_slack_no_jira(self):
        """Test when there's no Slack data and no Jira assignee/reporter."""
        jira_incident = {
            "id": "INC-123",
            "assignee": None,
            "assignee_email": None,
            "reporter": None,
            "reporter_email": None,
        }

        # Mock SlackService to return empty list
        with patch(
            "firetower.incidents.transformers.SlackService"
        ) as mock_slack_service:
            mock_service_instance = MagicMock()
            mock_slack_service.return_value = mock_service_instance
            mock_service_instance.get_channel_participants.return_value = []

            participants = extract_participants(jira_incident)

            # Should return empty list
            assert len(participants) == 0

    def test_extract_participants_uses_correct_channel_name(self):
        """Test that the correct channel name is used for Slack lookup."""
        jira_incident = {
            "id": "INC-456",
            "assignee": "John Smith",
            "assignee_email": "john.smith@example.com",
            "reporter": None,
            "reporter_email": None,
        }

        # Mock SlackService
        with patch(
            "firetower.incidents.transformers.SlackService"
        ) as mock_slack_service:
            mock_service_instance = MagicMock()
            mock_slack_service.return_value = mock_service_instance
            mock_service_instance.get_channel_participants.return_value = []

            extract_participants(jira_incident)

            # Verify get_channel_participants was called with lowercase incident ID
            mock_service_instance.get_channel_participants.assert_called_once_with(
                "inc-456"
            )

    def test_extract_participants_email_case_insensitive(self):
        """Test that email matching is case-insensitive."""
        jira_incident = {
            "id": "INC-123",
            "assignee": "John Smith",
            "assignee_email": "John.Smith@EXAMPLE.COM",  # Mixed case
            "reporter": None,
            "reporter_email": None,
        }

        # Mock SlackService
        with patch(
            "firetower.incidents.transformers.SlackService"
        ) as mock_slack_service:
            mock_service_instance = MagicMock()
            mock_slack_service.return_value = mock_service_instance

            mock_service_instance.get_channel_participants.return_value = [
                {
                    "name": "John Smith",
                    "email": "john.smith@example.com",  # lowercase
                    "avatar_url": "https://avatars.slack-edge.com/U123456_48.jpg",
                    "role": None,
                },
            ]

            participants = extract_participants(jira_incident)

            # Should match despite case difference
            assert len(participants) == 1
            assert participants[0]["role"] == "Captain"
            assert participants[0]["name"] == "John Smith"
