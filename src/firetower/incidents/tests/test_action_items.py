from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from firetower.auth.models import ExternalProfile, ExternalProfileType, UserProfile
from firetower.incidents.models import (
    ActionItem,
    ActionItemStatus,
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from firetower.incidents.services import (
    ActionItemsSyncStats,
    sync_action_items_from_linear,
)
from firetower.integrations.services.linear import LinearService


def _make_linear_issue(
    id="issue-1",
    identifier="ENG-123",
    title="Fix the bug",
    url="https://linear.app/team/issue/ENG-123",
    status="Todo",
    assignee_email=None,
):
    return {
        "id": id,
        "identifier": identifier,
        "title": title,
        "url": url,
        "status": status,
        "assignee_email": assignee_email,
    }


@pytest.mark.django_db
class TestSyncActionItemsFromLinear:
    def test_creates_action_items_from_linear(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        issues = [
            _make_linear_issue(id="id-1", identifier="ENG-1", title="Task 1"),
            _make_linear_issue(id="id-2", identifier="ENG-2", title="Task 2"),
        ]

        with patch(
            "firetower.incidents.services._linear_service.get_issues_by_attachment_url"
        ) as mock_fetch:
            mock_fetch.return_value = issues

            stats = sync_action_items_from_linear(incident, force=True)

            assert stats.created == 2
            assert stats.updated == 0
            assert stats.deleted == 0
            assert stats.skipped is False
            assert incident.action_items.count() == 2
            assert incident.action_items_last_synced_at is not None

    def test_updates_existing_action_items(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        ActionItem.objects.create(
            incident=incident,
            linear_issue_id="id-1",
            linear_identifier="ENG-1",
            title="Old title",
            status=ActionItemStatus.TODO,
            url="https://linear.app/team/issue/ENG-1",
        )

        issues = [
            _make_linear_issue(
                id="id-1",
                identifier="ENG-1",
                title="New title",
                status="In Progress",
            ),
        ]

        with patch(
            "firetower.incidents.services._linear_service.get_issues_by_attachment_url"
        ) as mock_fetch:
            mock_fetch.return_value = issues

            stats = sync_action_items_from_linear(incident, force=True)

            assert stats.created == 0
            assert stats.updated == 1
            item = incident.action_items.get(linear_issue_id="id-1")
            assert item.title == "New title"
            assert item.status == "In Progress"

    def test_deletes_stale_action_items(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        ActionItem.objects.create(
            incident=incident,
            linear_issue_id="id-stale",
            linear_identifier="ENG-99",
            title="Stale item",
            status=ActionItemStatus.TODO,
            url="https://linear.app/team/issue/ENG-99",
        )

        issues = [
            _make_linear_issue(id="id-new", identifier="ENG-1", title="New item"),
        ]

        with patch(
            "firetower.incidents.services._linear_service.get_issues_by_attachment_url"
        ) as mock_fetch:
            mock_fetch.return_value = issues

            stats = sync_action_items_from_linear(incident, force=True)

            assert stats.created == 1
            assert stats.deleted == 1
            assert not ActionItem.objects.filter(linear_issue_id="id-stale").exists()

    def test_throttle_skips_recent_sync(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            action_items_last_synced_at=timezone.now() - timedelta(seconds=30),
        )

        stats = sync_action_items_from_linear(incident)

        assert stats.skipped is True
        assert stats.created == 0

    def test_force_bypasses_throttle(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            action_items_last_synced_at=timezone.now() - timedelta(seconds=30),
        )

        with patch(
            "firetower.incidents.services._linear_service.get_issues_by_attachment_url"
        ) as mock_fetch:
            mock_fetch.return_value = []

            stats = sync_action_items_from_linear(incident, force=True)

            assert stats.skipped is False
            mock_fetch.assert_called_once()

    def test_handles_linear_api_failure(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        with patch(
            "firetower.incidents.services._linear_service.get_issues_by_attachment_url"
        ) as mock_fetch:
            mock_fetch.return_value = None

            stats = sync_action_items_from_linear(incident, force=True)

            assert len(stats.errors) == 1
            assert "Failed to fetch" in stats.errors[0]

    def test_resolves_assignee_by_email(self):
        user = User.objects.create_user(
            username="dev@example.com",
            email="dev@example.com",
        )

        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        issues = [
            _make_linear_issue(
                id="id-1",
                identifier="ENG-1",
                title="Task 1",
                assignee_email="dev@example.com",
            ),
        ]

        with patch(
            "firetower.incidents.services._linear_service.get_issues_by_attachment_url"
        ) as mock_fetch:
            mock_fetch.return_value = issues

            sync_action_items_from_linear(incident, force=True)

            item = incident.action_items.get(linear_issue_id="id-1")
            assert item.assignee == user
            assert ExternalProfile.objects.filter(
                user=user, type=ExternalProfileType.LINEAR
            ).exists()

    def test_creates_user_for_unknown_assignee_email(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        issues = [
            _make_linear_issue(
                id="id-1",
                identifier="ENG-1",
                title="Task 1",
                assignee_email="newdev@example.com",
            ),
        ]

        with patch(
            "firetower.incidents.services._linear_service.get_issues_by_attachment_url"
        ) as mock_fetch:
            mock_fetch.return_value = issues

            sync_action_items_from_linear(incident, force=True)

            item = incident.action_items.get(linear_issue_id="id-1")
            assert item.assignee is not None
            assert item.assignee.email == "newdev@example.com"
            assert ExternalProfile.objects.filter(
                user=item.assignee, type=ExternalProfileType.LINEAR
            ).exists()


@pytest.mark.django_db
class TestLinearService:
    def test_graphql_returns_none_without_api_key(self):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {}
            service = LinearService()
            result = service._graphql("query { viewer { id } }")
            assert result is None

    def test_get_issues_maps_state_types(self):
        mock_response = {
            "attachments": {
                "nodes": [
                    {
                        "issue": {
                            "id": "id-1",
                            "identifier": "ENG-1",
                            "title": "Started task",
                            "url": "https://linear.app/t/ENG-1",
                            "state": {"type": "started"},
                            "assignee": None,
                        }
                    },
                    {
                        "issue": {
                            "id": "id-2",
                            "identifier": "ENG-2",
                            "title": "Done task",
                            "url": "https://linear.app/t/ENG-2",
                            "state": {"type": "completed"},
                            "assignee": {"email": "dev@example.com"},
                        }
                    },
                    {
                        "issue": {
                            "id": "id-3",
                            "identifier": "ENG-3",
                            "title": "Cancelled task",
                            "url": "https://linear.app/t/ENG-3",
                            "state": {"type": "cancelled"},
                            "assignee": None,
                        }
                    },
                ]
            }
        }

        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {"API_KEY": "test-key"}
            service = LinearService()

        with patch.object(service, "_graphql", return_value=mock_response):
            issues = service.get_issues_by_attachment_url("INC-2000")

            assert issues is not None
            assert len(issues) == 3
            assert issues[0]["status"] == "In Progress"
            assert issues[1]["status"] == "Done"
            assert issues[1]["assignee_email"] == "dev@example.com"
            assert issues[2]["status"] == "Cancelled"

    def test_get_issues_deduplicates(self):
        mock_response = {
            "attachments": {
                "nodes": [
                    {
                        "issue": {
                            "id": "id-1",
                            "identifier": "ENG-1",
                            "title": "Task",
                            "url": "https://linear.app/t/ENG-1",
                            "state": {"type": "unstarted"},
                            "assignee": None,
                        }
                    },
                    {
                        "issue": {
                            "id": "id-1",
                            "identifier": "ENG-1",
                            "title": "Task",
                            "url": "https://linear.app/t/ENG-1",
                            "state": {"type": "unstarted"},
                            "assignee": None,
                        }
                    },
                ]
            }
        }

        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {"API_KEY": "test-key"}
            service = LinearService()

        with patch.object(service, "_graphql", return_value=mock_response):
            issues = service.get_issues_by_attachment_url("INC-2000")
            assert len(issues) == 1


@pytest.mark.django_db
class TestActionItemViews:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

    def test_list_action_items(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        ActionItem.objects.create(
            incident=incident,
            linear_issue_id="id-1",
            linear_identifier="ENG-1",
            title="Task 1",
            status=ActionItemStatus.TODO,
            url="https://linear.app/t/ENG-1",
        )

        with patch("firetower.incidents.views.sync_action_items_from_linear"):
            response = self.client.get(
                f"/api/ui/incidents/{incident.incident_number}/action-items/"
            )

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["linear_identifier"] == "ENG-1"
        assert response.data[0]["title"] == "Task 1"

    def test_list_action_items_includes_assignee_info(self):
        user = User.objects.create_user(
            username="dev@example.com",
            email="dev@example.com",
            first_name="Jane",
            last_name="Dev",
        )
        UserProfile.objects.filter(user=user).update(
            avatar_url="https://example.com/avatar.jpg"
        )

        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        ActionItem.objects.create(
            incident=incident,
            linear_issue_id="id-1",
            linear_identifier="ENG-1",
            title="Task 1",
            status=ActionItemStatus.TODO,
            assignee=user,
            url="https://linear.app/t/ENG-1",
        )

        with patch("firetower.incidents.views.sync_action_items_from_linear"):
            response = self.client.get(
                f"/api/ui/incidents/{incident.incident_number}/action-items/"
            )

        assert response.status_code == 200
        assert response.data[0]["assignee_name"] == "Jane Dev"
        assert (
            response.data[0]["assignee_avatar_url"] == "https://example.com/avatar.jpg"
        )

    def test_force_sync_action_items(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        with patch(
            "firetower.incidents.views.sync_action_items_from_linear"
        ) as mock_sync:
            mock_sync.return_value = ActionItemsSyncStats(created=1)

            response = self.client.post(
                f"/api/incidents/{incident.incident_number}/sync-action-items/"
            )

        assert response.status_code == 200
        assert response.data["success"] is True
        assert response.data["stats"]["created"] == 1
        mock_sync.assert_called_once_with(incident, force=True)

    def test_action_items_respects_privacy(self):
        other_user = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
        )
        incident = Incident.objects.create(
            title="Private Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
            captain=other_user,
        )

        response = self.client.get(
            f"/api/ui/incidents/{incident.incident_number}/action-items/"
        )

        assert response.status_code == 404
