from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.incidents.models import (
    ActionItem,
    ActionItemStatus,
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from firetower.incidents.services import (
    _comment_parent_issue_completed,
    _update_parent_issue_status,
    sync_incident_participants_from_slack,
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
class TestUpdateParentIssueStatus:
    def _make_incident(self, status=IncidentStatus.ACTIVE):
        return Incident.objects.create(
            title="Test Incident",
            status=status,
            severity=IncidentSeverity.P1,
            linear_parent_issue_id="lin-123",
        )

    def _make_linear_service(self, current_state_type="unstarted"):
        svc = MagicMock()
        svc.get_workflow_states.return_value = {
            "started": "state-started",
            "completed": "state-completed",
        }
        svc.update_issue.return_value = True
        svc.get_issue.return_value = {"state_type": current_state_type}
        return svc

    @pytest.fixture(autouse=True)
    def _linear_settings(self, settings):
        settings.LINEAR = {
            "TEAM_ID": "team-1",
            "API_KEY": "key",
            "PARENT_STATUS_COMMENT_COMPLETED": "completed comment",
        }

    def _add_item(self, incident, status, suffix="1"):
        return ActionItem.objects.create(
            incident=incident,
            linear_issue_id=f"li-{suffix}",
            linear_identifier=f"INC-{suffix}",
            title=f"Item {suffix}",
            status=status,
            url=f"https://linear.app/issue/{suffix}",
        )

    def test_active_incident_no_action_items_does_nothing(self):
        incident = self._make_incident(status=IncidentStatus.ACTIVE)
        svc = self._make_linear_service()

        _update_parent_issue_status(incident, svc)

        svc.update_issue.assert_not_called()
        svc.create_comment.assert_not_called()

    def test_active_incident_all_items_done_does_nothing(self):
        incident = self._make_incident(status=IncidentStatus.ACTIVE)
        self._add_item(incident, ActionItemStatus.DONE)
        svc = self._make_linear_service()

        _update_parent_issue_status(incident, svc)

        svc.update_issue.assert_not_called()
        svc.create_comment.assert_not_called()

    def test_mitigated_incident_all_items_done_does_nothing(self):
        incident = self._make_incident(status=IncidentStatus.MITIGATED)
        self._add_item(incident, ActionItemStatus.DONE)
        svc = self._make_linear_service()

        _update_parent_issue_status(incident, svc)

        svc.update_issue.assert_not_called()
        svc.create_comment.assert_not_called()

    def test_done_incident_incomplete_items_does_nothing(self):
        incident = self._make_incident(status=IncidentStatus.DONE)
        self._add_item(incident, ActionItemStatus.DONE, "1")
        self._add_item(incident, ActionItemStatus.IN_PROGRESS, "2")
        svc = self._make_linear_service()

        _update_parent_issue_status(incident, svc)

        svc.update_issue.assert_not_called()
        svc.create_comment.assert_not_called()

    def test_done_incident_no_action_items_sets_completed(self):
        incident = self._make_incident(status=IncidentStatus.DONE)
        svc = self._make_linear_service()

        _update_parent_issue_status(incident, svc)

        svc.update_issue.assert_called_once_with("lin-123", state_id="state-completed")
        svc.create_comment.assert_called_once()

    def test_done_incident_all_items_done_sets_completed(self):
        incident = self._make_incident(status=IncidentStatus.DONE)
        self._add_item(incident, ActionItemStatus.DONE, "1")
        self._add_item(incident, ActionItemStatus.CANCELED, "2")
        svc = self._make_linear_service()

        _update_parent_issue_status(incident, svc)

        svc.update_issue.assert_called_once_with("lin-123", state_id="state-completed")
        svc.create_comment.assert_called_once()

    def test_canceled_incident_all_items_done_sets_completed(self):
        incident = self._make_incident(status=IncidentStatus.CANCELED)
        self._add_item(incident, ActionItemStatus.DONE)
        svc = self._make_linear_service()

        _update_parent_issue_status(incident, svc)

        svc.update_issue.assert_called_once_with("lin-123", state_id="state-completed")
        svc.create_comment.assert_called_once()

    def test_update_issue_failure_skips_comment(self):
        incident = self._make_incident(status=IncidentStatus.DONE)
        svc = self._make_linear_service()
        svc.update_issue.return_value = False

        _update_parent_issue_status(incident, svc)

        svc.update_issue.assert_called_once_with("lin-123", state_id="state-completed")
        svc.create_comment.assert_not_called()

    def test_skips_update_when_already_completed(self):
        incident = self._make_incident(status=IncidentStatus.DONE)
        svc = self._make_linear_service(current_state_type="completed")

        _update_parent_issue_status(incident, svc)

        svc.update_issue.assert_not_called()
        svc.create_comment.assert_not_called()

    def test_updates_when_in_different_state(self):
        incident = self._make_incident(status=IncidentStatus.DONE)
        svc = self._make_linear_service(current_state_type="started")

        _update_parent_issue_status(incident, svc)

        svc.update_issue.assert_called_once_with("lin-123", state_id="state-completed")
        svc.create_comment.assert_called_once()

    def test_skips_update_when_get_issue_fails(self):
        incident = self._make_incident(status=IncidentStatus.DONE)
        svc = self._make_linear_service()
        svc.get_issue.return_value = None

        _update_parent_issue_status(incident, svc)

        svc.update_issue.assert_not_called()
        svc.create_comment.assert_not_called()

    def test_never_reopens_when_item_reopens_after_completion(self):
        incident = self._make_incident(status=IncidentStatus.DONE)
        self._add_item(incident, ActionItemStatus.DONE, "1")
        self._add_item(incident, ActionItemStatus.IN_PROGRESS, "2")
        svc = self._make_linear_service(current_state_type="completed")

        _update_parent_issue_status(incident, svc)

        svc.update_issue.assert_not_called()
        svc.create_comment.assert_not_called()


@pytest.mark.django_db
class TestCommentParentIssueCompleted:
    def _make_incident(self, status=IncidentStatus.DONE):
        return Incident.objects.create(
            title="Test Incident",
            status=status,
            severity=IncidentSeverity.P1,
            linear_parent_issue_id="lin-123",
        )

    @pytest.fixture(autouse=True)
    def _linear_settings(self, settings):
        settings.LINEAR = {
            "TEAM_ID": "team-1",
            "API_KEY": "key",
            "PARENT_STATUS_COMMENT_COMPLETED": (
                "Set to Completed. "
                "Incident {{ incident.incident_number }} is {{ incident.status }}. "
                "{{ completed_action_items }}/{{ total_action_items }} done."
            ),
        }

    def test_posts_completed_comment(self):
        incident = self._make_incident(status=IncidentStatus.DONE)
        svc = MagicMock()

        _comment_parent_issue_completed(incident, svc, ["Done", "Done"])

        svc.create_comment.assert_called_once_with(
            "lin-123",
            f"Set to Completed. Incident {incident.incident_number} is Done. 2/2 done.",
        )

    def test_counts_canceled_as_completed(self):
        incident = self._make_incident(status=IncidentStatus.DONE)
        svc = MagicMock()

        _comment_parent_issue_completed(incident, svc, ["Done", "Canceled"])

        svc.create_comment.assert_called_once_with(
            "lin-123",
            f"Set to Completed. Incident {incident.incident_number} is Done. 2/2 done.",
        )

    def test_empty_template_skips_comment(self, settings):
        settings.LINEAR["PARENT_STATUS_COMMENT_COMPLETED"] = ""
        incident = self._make_incident(status=IncidentStatus.DONE)
        svc = MagicMock()

        _comment_parent_issue_completed(incident, svc, ["Done"])

        svc.create_comment.assert_not_called()

    def test_whitespace_only_template_skips_comment(self, settings):
        settings.LINEAR["PARENT_STATUS_COMMENT_COMPLETED"] = "   "
        incident = self._make_incident(status=IncidentStatus.DONE)
        svc = MagicMock()

        _comment_parent_issue_completed(incident, svc, ["Done"])

        svc.create_comment.assert_not_called()

    def test_no_action_items(self):
        incident = self._make_incident(status=IncidentStatus.DONE)
        svc = MagicMock()

        _comment_parent_issue_completed(incident, svc, [])

        svc.create_comment.assert_called_once_with(
            "lin-123",
            f"Set to Completed. Incident {incident.incident_number} is Done. 0/0 done.",
        )

    def test_create_comment_failure_logs_and_continues(self):
        incident = self._make_incident(status=IncidentStatus.DONE)
        svc = MagicMock()
        svc.create_comment.return_value = False

        _comment_parent_issue_completed(incident, svc, ["Done"])

        svc.create_comment.assert_called_once()

    def test_create_comment_exception_logs_and_continues(self):
        incident = self._make_incident(status=IncidentStatus.DONE)
        svc = MagicMock()
        svc.create_comment.side_effect = Exception("API error")

        _comment_parent_issue_completed(incident, svc, ["Done"])

        svc.create_comment.assert_called_once()

    def test_template_render_error_logs_and_continues(self, settings):
        settings.LINEAR["PARENT_STATUS_COMMENT_COMPLETED"] = "{{ unterminated"
        incident = self._make_incident(status=IncidentStatus.DONE)
        svc = MagicMock()

        _comment_parent_issue_completed(incident, svc, ["Done"])

        svc.create_comment.assert_not_called()
