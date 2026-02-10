from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from firetower.incidents.services import (
    sync_incident_participants_from_slack,
    sync_incident_to_slack,
)


@pytest.mark.django_db
class TestSyncIncidentParticipantsFromSlack:
    def test_syncs_participants_from_slack_channel(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://workspace.slack.com/archives/C12345",
        )

        existing_user = User.objects.create_user(
            username="existing@example.com",
            email="existing@example.com",
        )
        incident.participants.add(existing_user)

        slack_user1 = User.objects.create_user(
            username="user1@example.com",
            email="user1@example.com",
        )
        ExternalProfile.objects.create(
            user=slack_user1,
            type=ExternalProfileType.SLACK,
            external_id="U11111",
        )

        slack_user2 = User.objects.create_user(
            username="user2@example.com",
            email="user2@example.com",
        )
        ExternalProfile.objects.create(
            user=slack_user2,
            type=ExternalProfileType.SLACK,
            external_id="U22222",
        )

        with patch(
            "firetower.incidents.services._slack_service.parse_channel_id_from_url"
        ) as mock_parse:
            mock_parse.return_value = "C12345"

            with patch(
                "firetower.incidents.services._slack_service.get_channel_members"
            ) as mock_get_members:
                mock_get_members.return_value = ["U11111", "U22222"]

                stats = sync_incident_participants_from_slack(incident)

                assert stats.added == 2
                assert stats.already_existed == 0
                assert stats.errors == []
                assert stats.skipped is False

                assert incident.participants.count() == 3
                assert slack_user1 in incident.participants.all()
                assert slack_user2 in incident.participants.all()
                assert existing_user in incident.participants.all()

                assert incident.participants_last_synced_at is not None

    def test_push_only_preserves_existing_participants(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://workspace.slack.com/archives/C12345",
        )

        manual_user = User.objects.create_user(
            username="manual@example.com",
            email="manual@example.com",
        )
        incident.participants.add(manual_user)

        slack_user = User.objects.create_user(
            username="user1@example.com",
            email="user1@example.com",
        )
        ExternalProfile.objects.create(
            user=slack_user,
            type=ExternalProfileType.SLACK,
            external_id="U11111",
        )

        with patch(
            "firetower.incidents.services._slack_service.parse_channel_id_from_url"
        ) as mock_parse:
            mock_parse.return_value = "C12345"

            with patch(
                "firetower.incidents.services._slack_service.get_channel_members"
            ) as mock_get_members:
                mock_get_members.return_value = ["U11111"]

                sync_incident_participants_from_slack(incident)

                assert incident.participants.count() == 2
                assert manual_user in incident.participants.all()
                assert slack_user in incident.participants.all()

    def test_throttle_skips_recent_sync(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            participants_last_synced_at=timezone.now() - timedelta(seconds=30),
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://workspace.slack.com/archives/C12345",
        )

        stats = sync_incident_participants_from_slack(incident)

        assert stats.skipped is True
        assert stats.added == 0

    def test_force_bypasses_throttle(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            participants_last_synced_at=timezone.now() - timedelta(seconds=30),
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://workspace.slack.com/archives/C12345",
        )

        slack_user = User.objects.create_user(
            username="user1@example.com",
            email="user1@example.com",
        )
        ExternalProfile.objects.create(
            user=slack_user,
            type=ExternalProfileType.SLACK,
            external_id="U11111",
        )

        with patch(
            "firetower.incidents.services._slack_service.parse_channel_id_from_url"
        ) as mock_parse:
            mock_parse.return_value = "C12345"

            with patch(
                "firetower.incidents.services._slack_service.get_channel_members"
            ) as mock_get_members:
                mock_get_members.return_value = ["U11111"]

                stats = sync_incident_participants_from_slack(incident, force=True)

                assert stats.skipped is False
                assert stats.added == 1

    def test_handles_missing_slack_link(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        stats = sync_incident_participants_from_slack(incident)

        assert stats.added == 0
        assert len(stats.errors) == 1
        assert "No Slack link" in stats.errors[0]

    def test_handles_invalid_channel_url(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://invalid-url.com",
        )

        with patch(
            "firetower.incidents.services._slack_service.parse_channel_id_from_url"
        ) as mock_parse:
            mock_parse.return_value = None

            stats = sync_incident_participants_from_slack(incident)

            assert stats.added == 0
            assert len(stats.errors) == 1
            assert "Could not parse channel ID" in stats.errors[0]

    def test_handles_slack_api_failure(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://workspace.slack.com/archives/C12345",
        )

        with patch(
            "firetower.incidents.services._slack_service.parse_channel_id_from_url"
        ) as mock_parse:
            mock_parse.return_value = "C12345"

            with patch(
                "firetower.incidents.services._slack_service.get_channel_members"
            ) as mock_get_members:
                mock_get_members.return_value = None

                stats = sync_incident_participants_from_slack(incident)

                assert stats.added == 0
                assert len(stats.errors) == 1
                assert "Failed to fetch channel members" in stats.errors[0]

    def test_handles_user_creation_failure(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://workspace.slack.com/archives/C12345",
        )

        with patch(
            "firetower.incidents.services._slack_service.parse_channel_id_from_url"
        ) as mock_parse:
            mock_parse.return_value = "C12345"

            with patch(
                "firetower.incidents.services._slack_service.get_channel_members"
            ) as mock_get_members:
                mock_get_members.return_value = ["U_INVALID"]

                with patch(
                    "firetower.incidents.services.get_or_create_user_from_slack_id"
                ) as mock_get_user:
                    mock_get_user.return_value = None

                    stats = sync_incident_participants_from_slack(incident)

                    assert stats.added == 0
                    assert len(stats.errors) == 1
                    assert "Could not get/create user" in stats.errors[0]

    def test_counts_already_existed_participants(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://workspace.slack.com/archives/C12345",
        )

        slack_user = User.objects.create_user(
            username="user1@example.com",
            email="user1@example.com",
        )
        ExternalProfile.objects.create(
            user=slack_user,
            type=ExternalProfileType.SLACK,
            external_id="U11111",
        )
        incident.participants.add(slack_user)

        with patch(
            "firetower.incidents.services._slack_service.parse_channel_id_from_url"
        ) as mock_parse:
            mock_parse.return_value = "C12345"

            with patch(
                "firetower.incidents.services._slack_service.get_channel_members"
            ) as mock_get_members:
                mock_get_members.return_value = ["U11111"]

                stats = sync_incident_participants_from_slack(incident)

                assert stats.added == 0
                assert stats.already_existed == 1
                assert incident.participants.count() == 1

    def test_skips_bots(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://workspace.slack.com/archives/C12345",
        )

        slack_user = User.objects.create_user(
            username="user1@example.com",
            email="user1@example.com",
        )
        ExternalProfile.objects.create(
            user=slack_user,
            type=ExternalProfileType.SLACK,
            external_id="U11111",
        )

        with patch(
            "firetower.incidents.services._slack_service.parse_channel_id_from_url"
        ) as mock_parse:
            mock_parse.return_value = "C12345"

            with patch(
                "firetower.incidents.services._slack_service.get_channel_members"
            ) as mock_get_members:
                mock_get_members.return_value = ["U11111", "B12345", "BSLACKBOT"]

                with patch(
                    "firetower.incidents.services.get_or_create_user_from_slack_id"
                ) as mock_get_user:
                    mock_get_user.return_value = slack_user

                    stats = sync_incident_participants_from_slack(incident)

                    assert mock_get_user.call_count == 1
                    mock_get_user.assert_called_once_with("U11111")
                    assert stats.added == 1
                    assert stats.errors == []


@pytest.mark.django_db
class TestSyncIncidentToSlack:
    def test_syncs_topic_to_slack_channel_with_slack_profile(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Captain",
            last_name="One",
        )
        ExternalProfile.objects.create(
            user=captain,
            type=ExternalProfileType.SLACK,
            external_id="U99999",
        )
        incident.captain = captain
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://workspace.slack.com/archives/C12345",
        )

        with patch(
            "firetower.incidents.services._slack_service.update_channel_topic"
        ) as mock_update:
            mock_update.return_value = True
            sync_incident_to_slack(incident)

            mock_update.assert_called_once_with(
                "C12345",
                f"[P1] {incident.incident_number} Test Incident | IC: <@U99999>",
            )

    def test_syncs_topic_falls_back_to_full_name_without_slack_profile(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Captain",
            last_name="One",
        )
        incident.captain = captain
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://workspace.slack.com/archives/C12345",
        )

        with patch(
            "firetower.incidents.services._slack_service.update_channel_topic"
        ) as mock_update:
            mock_update.return_value = True
            sync_incident_to_slack(incident)

            mock_update.assert_called_once_with(
                "C12345",
                f"[P1] {incident.incident_number} Test Incident | IC: Captain One",
            )

    def test_skips_if_no_slack_link(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Captain",
            last_name="One",
        )
        incident.captain = captain

        sync_incident_to_slack(incident)

    def test_handles_invalid_channel_url(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Captain",
            last_name="One",
        )
        incident.captain = captain
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://invalid-url.com",
        )

        sync_incident_to_slack(incident)

    def test_handles_slack_api_failure(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Captain",
            last_name="One",
        )
        incident.captain = captain
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://workspace.slack.com/archives/C12345",
        )

        with patch(
            "firetower.incidents.services._slack_service.update_channel_topic"
        ) as mock_update:
            mock_update.return_value = False

            sync_incident_to_slack(incident)
