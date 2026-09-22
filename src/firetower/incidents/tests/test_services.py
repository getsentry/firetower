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
    sync_linear_parent_issue_status,
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

    def test_skips_unresolvable_users(self):
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
                    assert stats.errors == []

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

    def test_skips_inactive_users(self):
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

        active_user = User.objects.create_user(
            username="active@example.com",
            email="active@example.com",
        )
        ExternalProfile.objects.create(
            user=active_user,
            type=ExternalProfileType.SLACK,
            external_id="U_ACTIVE",
        )

        inactive_user = User.objects.create(
            username="slack:U_BOT",
            is_active=False,
        )
        ExternalProfile.objects.create(
            user=inactive_user,
            type=ExternalProfileType.SLACK,
            external_id="U_BOT",
        )

        with patch(
            "firetower.incidents.services._slack_service.parse_channel_id_from_url"
        ) as mock_parse:
            mock_parse.return_value = "C12345"

            with patch(
                "firetower.incidents.services._slack_service.get_channel_members"
            ) as mock_get_members:
                mock_get_members.return_value = ["U_ACTIVE", "U_BOT"]

                stats = sync_incident_participants_from_slack(incident)

                assert stats.added == 1
                assert incident.participants.count() == 1
                assert active_user in incident.participants.all()
                assert inactive_user not in incident.participants.all()


@pytest.mark.django_db
class TestSyncLinearParentIssueStatus:
    def _make_incident(self, status=IncidentStatus.ACTIVE):
        return Incident.objects.create(
            title="Test Incident",
            status=status,
            severity=IncidentSeverity.P1,
            linear_parent_issue_id="lin-123",
        )

    @pytest.fixture(autouse=True)
    def _linear_settings(self, settings):
        settings.LINEAR = {"TEAM_ID": "team-1", "API_KEY": "key"}

    @pytest.mark.parametrize(
        ("incident_status", "target_state", "state_id"),
        [
            (IncidentStatus.ACTIVE, "in_progress", "state-in-progress"),
            (IncidentStatus.MITIGATED, "in_progress", "state-in-progress"),
            (IncidentStatus.POSTMORTEM, "in_review", "state-in-review"),
            (IncidentStatus.DONE, "done", "state-done"),
            (IncidentStatus.CANCELED, "canceled", "state-canceled"),
        ],
    )
    def test_mirrors_incident_status(self, incident_status, target_state, state_id):
        incident = self._make_incident(status=incident_status)

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            service = mock_get.return_value
            service.get_workflow_states.return_value = {
                "in_progress": "state-in-progress",
                "in_review": "state-in-review",
                "done": "state-done",
                "canceled": "state-canceled",
            }
            service.get_issue.return_value = {"state_id": "state-unstarted"}
            service.update_issue.return_value = True

            sync_linear_parent_issue_status(incident)

        service.update_issue.assert_called_once_with("lin-123", state_id=state_id)

    def test_ignores_action_items(self):
        incident = self._make_incident(status=IncidentStatus.DONE)

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            service = mock_get.return_value
            service.get_workflow_states.return_value = {"done": "state-done"}
            service.get_issue.return_value = {"state_id": "state-in-progress"}
            service.update_issue.return_value = True

            sync_linear_parent_issue_status(incident)

        service.update_issue.assert_called_once_with("lin-123", state_id="state-done")

    def test_reopens_a_canceled_parent_when_incident_reopens(self):
        incident = self._make_incident(status=IncidentStatus.ACTIVE)

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            service = mock_get.return_value
            service.get_workflow_states.return_value = {
                "in_progress": "state-in-progress"
            }
            service.get_issue.return_value = {"state_id": "state-canceled"}
            service.update_issue.return_value = True

            sync_linear_parent_issue_status(incident)

        service.update_issue.assert_called_once_with(
            "lin-123", state_id="state-in-progress"
        )

    def test_skips_update_when_parent_already_matches_incident(self):
        incident = self._make_incident(status=IncidentStatus.DONE)

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            service = mock_get.return_value
            service.get_workflow_states.return_value = {"done": "state-done"}
            service.get_issue.return_value = {"state_id": "state-done"}

            sync_linear_parent_issue_status(incident)

        service.update_issue.assert_not_called()

    def test_reopens_an_in_review_parent_when_incident_reopens(self):
        incident = self._make_incident(status=IncidentStatus.ACTIVE)

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            service = mock_get.return_value
            service.get_workflow_states.return_value = {
                "in_progress": "state-in-progress"
            }
            service.get_issue.return_value = {"state_id": "state-in-review"}
            service.update_issue.return_value = True

            sync_linear_parent_issue_status(incident)

        service.update_issue.assert_called_once_with(
            "lin-123", state_id="state-in-progress"
        )

    def test_skips_update_when_parent_cannot_be_found(self):
        incident = self._make_incident()

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            service = mock_get.return_value
            service.get_workflow_states.return_value = {
                "in_progress": "state-in-progress"
            }
            service.get_issue.return_value = None

            sync_linear_parent_issue_status(incident)

        service.update_issue.assert_not_called()
