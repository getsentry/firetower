from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from firetower.auth.models import ExternalProfile, ExternalProfileType, UserProfile
from firetower.incidents.hooks import (
    create_linear_parent_issue,
    on_title_changed,
    on_visibility_changed,
)
from firetower.incidents.models import (
    ActionItem,
    ActionItemRelationType,
    ActionItemStatus,
    ExternalLink,
    ExternalLinkType,
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
    relation_type="child",
    assignee_email=None,
    assignee_linear_id=None,
    priority=0,
):
    return {
        "id": id,
        "identifier": identifier,
        "title": title,
        "url": url,
        "status": status,
        "relation_type": relation_type,
        "assignee_email": assignee_email,
        "assignee_linear_id": assignee_linear_id,
        "priority": priority,
    }


@pytest.mark.django_db
class TestSyncActionItemsFromLinear:
    def _make_incident(self, **kwargs):
        defaults = {
            "title": "Test Incident",
            "status": IncidentStatus.ACTIVE,
            "severity": IncidentSeverity.P1,
            "linear_parent_issue_id": "parent-issue-id",
        }
        defaults.update(kwargs)
        return Incident.objects.create(**defaults)

    def test_skips_when_no_parent_issue(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        stats = sync_action_items_from_linear(incident, force=True)

        assert stats.skipped is True
        assert stats.created == 0

    def test_creates_action_items_from_children(self):
        incident = self._make_incident()

        children = [
            _make_linear_issue(id="id-1", identifier="ENG-1", title="Task 1"),
            _make_linear_issue(id="id-2", identifier="ENG-2", title="Task 2"),
        ]

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_get.return_value.get_child_issues.return_value = children
            mock_get.return_value.get_workflow_states.return_value = None

            stats = sync_action_items_from_linear(incident, force=True)

            assert stats.created == 2
            assert stats.updated == 0
            assert stats.deleted == 0
            assert incident.action_items.count() == 2
            assert incident.action_items_last_synced_at is not None

    def test_ignores_related_issues(self):
        incident = self._make_incident()

        children = [
            _make_linear_issue(id="id-1", identifier="ENG-1", title="Child task"),
        ]

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_service = mock_get.return_value
            mock_service.get_child_issues.return_value = children
            mock_service.get_workflow_states.return_value = None

            stats = sync_action_items_from_linear(incident, force=True)

            assert stats.created == 1
            assert incident.action_items.count() == 1
            item = incident.action_items.get(linear_issue_id="id-1")
            assert item.relation_type == ActionItemRelationType.CHILD
            mock_service.get_related_issues.assert_not_called()

    def test_same_issue_on_multiple_incidents(self):
        incident_a = self._make_incident(linear_parent_issue_id="parent-a")
        incident_b = self._make_incident(linear_parent_issue_id="parent-b")

        shared_issue = [
            _make_linear_issue(id="shared-1", identifier="ENG-99", title="Shared task"),
        ]

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_get.return_value.get_child_issues.return_value = shared_issue
            mock_get.return_value.get_workflow_states.return_value = None

            sync_action_items_from_linear(incident_a, force=True)
            sync_action_items_from_linear(incident_b, force=True)

        assert incident_a.action_items.filter(linear_issue_id="shared-1").exists()
        assert incident_b.action_items.filter(linear_issue_id="shared-1").exists()
        assert ActionItem.objects.filter(linear_issue_id="shared-1").count() == 2

    def test_updates_existing_action_items(self):
        incident = self._make_incident()
        ActionItem.objects.create(
            incident=incident,
            linear_issue_id="id-1",
            linear_identifier="ENG-1",
            title="Old title",
            status=ActionItemStatus.TODO,
            url="https://linear.app/team/issue/ENG-1",
        )

        children = [
            _make_linear_issue(
                id="id-1",
                identifier="ENG-1",
                title="New title",
                status="In Progress",
            ),
        ]

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_get.return_value.get_child_issues.return_value = children
            mock_get.return_value.get_workflow_states.return_value = None

            stats = sync_action_items_from_linear(incident, force=True)

            assert stats.created == 0
            assert stats.updated == 1
            item = incident.action_items.get(linear_issue_id="id-1")
            assert item.title == "New title"
            assert item.status == "In Progress"

    def test_deletes_stale_action_items(self):
        incident = self._make_incident()
        ActionItem.objects.create(
            incident=incident,
            linear_issue_id="id-stale",
            linear_identifier="ENG-99",
            title="Stale item",
            status=ActionItemStatus.TODO,
            url="https://linear.app/team/issue/ENG-99",
        )

        children = [
            _make_linear_issue(id="id-new", identifier="ENG-1", title="New item"),
        ]

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_get.return_value.get_child_issues.return_value = children
            mock_get.return_value.get_workflow_states.return_value = None

            stats = sync_action_items_from_linear(incident, force=True)

            assert stats.created == 1
            assert stats.deleted == 1
            assert not ActionItem.objects.filter(linear_issue_id="id-stale").exists()

    def test_throttle_skips_recent_sync(self):
        incident = self._make_incident(
            action_items_last_synced_at=timezone.now() - timedelta(seconds=30),
        )

        stats = sync_action_items_from_linear(incident)

        assert stats.skipped is True
        assert stats.created == 0

    def test_force_bypasses_throttle(self):
        incident = self._make_incident(
            action_items_last_synced_at=timezone.now() - timedelta(seconds=30),
        )

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_get.return_value.get_child_issues.return_value = []
            mock_get.return_value.get_workflow_states.return_value = None

            stats = sync_action_items_from_linear(incident, force=True)

            assert stats.skipped is False
            mock_get.return_value.get_child_issues.assert_called_once()

    def test_handles_children_api_failure(self):
        incident = self._make_incident()

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_get.return_value.get_child_issues.return_value = None

            stats = sync_action_items_from_linear(incident, force=True)

            assert len(stats.errors) == 1
            assert "child issues" in stats.errors[0]
            incident.refresh_from_db()
            assert incident.action_items_last_synced_at is not None

    def test_resolves_assignee_by_email(self):
        user = User.objects.create_user(
            username="dev@example.com",
            email="dev@example.com",
        )

        incident = self._make_incident()

        children = [
            _make_linear_issue(
                id="id-1",
                identifier="ENG-1",
                title="Task 1",
                assignee_email="dev@example.com",
                assignee_linear_id="linear-user-123",
            ),
        ]

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_get.return_value.get_child_issues.return_value = children
            mock_get.return_value.get_workflow_states.return_value = None

            sync_action_items_from_linear(incident, force=True)

            item = incident.action_items.get(linear_issue_id="id-1")
            assert item.assignee == user
            profile = ExternalProfile.objects.get(
                user=user, type=ExternalProfileType.LINEAR
            )
            assert profile.external_id == "linear-user-123"

    def test_creates_user_for_unknown_assignee_email(self):
        incident = self._make_incident()

        children = [
            _make_linear_issue(
                id="id-1",
                identifier="ENG-1",
                title="Task 1",
                assignee_email="newdev@example.com",
                assignee_linear_id="linear-user-456",
            ),
        ]

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_get.return_value.get_child_issues.return_value = children
            mock_get.return_value.get_workflow_states.return_value = None

            sync_action_items_from_linear(incident, force=True)

            item = incident.action_items.get(linear_issue_id="id-1")
            assert item.assignee is not None
            assert item.assignee.email == "newdev@example.com"
            profile = ExternalProfile.objects.get(
                user=item.assignee, type=ExternalProfileType.LINEAR
            )
            assert profile.external_id == "linear-user-456"

    def test_backfill_creates_parent_and_syncs(self, settings):
        settings.LINEAR = {"TEAM_ID": "team-1"}
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        children = [
            _make_linear_issue(id="id-1", identifier="ENG-1", title="Task 1"),
        ]

        def fake_create_parent(inc):
            inc.linear_parent_issue_id = "backfilled-parent-id"
            inc.save(update_fields=["linear_parent_issue_id"])

        with (
            patch(
                "firetower.incidents.hooks.create_linear_parent_issue",
                side_effect=fake_create_parent,
            ) as mock_create_parent,
            patch("firetower.incidents.services._get_linear_service") as mock_get,
        ):
            mock_get.return_value.get_child_issues.return_value = children
            mock_get.return_value.get_workflow_states.return_value = None

            stats = sync_action_items_from_linear(incident, force=True)

            mock_create_parent.assert_called_once_with(incident)
            assert stats.skipped is False
            assert stats.created == 1
            assert incident.action_items.count() == 1

    def test_auto_completes_parent_when_all_done(self, settings):
        settings.LINEAR = {"TEAM_ID": "team-1"}
        incident = self._make_incident(status=IncidentStatus.DONE)

        children = [
            _make_linear_issue(
                id="id-1", identifier="ENG-1", title="T1", status="Done"
            ),
            _make_linear_issue(
                id="id-2", identifier="ENG-2", title="T2", status="Canceled"
            ),
        ]

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_service = mock_get.return_value
            mock_service.get_child_issues.return_value = children
            mock_service.get_workflow_states.return_value = {
                "completed": "state-done",
                "backlog": "state-backlog",
            }
            mock_service.update_issue.return_value = True

            sync_action_items_from_linear(incident, force=True)

            mock_service.update_issue.assert_any_call(
                "parent-issue-id", state_id="state-done"
            )

    def test_sets_parent_to_started_when_incomplete_items(self, settings):
        settings.LINEAR = {"TEAM_ID": "team-1"}
        incident = self._make_incident(status=IncidentStatus.DONE)

        children = [
            _make_linear_issue(
                id="id-1", identifier="ENG-1", title="T1", status="Done"
            ),
            _make_linear_issue(
                id="id-2", identifier="ENG-2", title="T2", status="In Progress"
            ),
        ]

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_service = mock_get.return_value
            mock_service.get_child_issues.return_value = children
            mock_service.get_workflow_states.return_value = {
                "completed": "state-done",
                "started": "state-started",
            }
            mock_service.update_issue.return_value = True

            sync_action_items_from_linear(incident, force=True)

            mock_service.update_issue.assert_any_call(
                "parent-issue-id", state_id="state-started"
            )

    def test_completes_parent_when_no_action_items(self, settings):
        settings.LINEAR = {"TEAM_ID": "team-1"}
        incident = self._make_incident(status=IncidentStatus.DONE)

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_service = mock_get.return_value
            mock_service.get_child_issues.return_value = []
            mock_service.get_workflow_states.return_value = {
                "completed": "state-done",
                "backlog": "state-backlog",
            }
            mock_service.update_issue.return_value = True

            sync_action_items_from_linear(incident, force=True)

            mock_service.update_issue.assert_any_call(
                "parent-issue-id", state_id="state-done"
            )

    def test_does_not_push_parent_assignee_on_sync(self, settings):
        settings.LINEAR = {"TEAM_ID": "team-1"}
        captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
        )
        ExternalProfile.objects.create(
            user=captain,
            type=ExternalProfileType.LINEAR,
            external_id="linear-captain-id",
        )
        incident = self._make_incident(captain=captain)

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_service = mock_get.return_value
            mock_service.get_child_issues.return_value = []
            mock_service.get_workflow_states.return_value = None
            mock_service.update_issue.return_value = True

            sync_action_items_from_linear(incident, force=True)

            for call in mock_service.update_issue.call_args_list:
                assert "assignee_id" not in call.kwargs


@pytest.mark.django_db
class TestLinearService:
    def test_graphql_returns_none_without_credentials(self):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {}
            service = LinearService()
            result = service._graphql("query { viewer { id } }")
            assert result is None

    def test_create_issue(self):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {
                "CLIENT_ID": "test-id",
                "CLIENT_SECRET": "test-secret",
            }
            service = LinearService()

        mock_response = {
            "issueCreate": {
                "success": True,
                "issue": {
                    "id": "issue-uuid",
                    "identifier": "ENG-100",
                    "url": "https://linear.app/t/ENG-100",
                },
            }
        }

        with patch.object(service, "_graphql", return_value=mock_response):
            result = service.create_issue("Title", "Desc", "team-1")

            assert result is not None
            assert result["id"] == "issue-uuid"
            assert result["identifier"] == "ENG-100"

    def test_create_issue_with_project(self):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {
                "CLIENT_ID": "test-id",
                "CLIENT_SECRET": "test-secret",
            }
            service = LinearService()

        with patch.object(
            service,
            "_graphql",
            return_value={
                "issueCreate": {
                    "success": True,
                    "issue": {"id": "id", "identifier": "E-1", "url": "url"},
                }
            },
        ) as mock_gql:
            service.create_issue("Title", "Desc", "team-1", "project-1")

            call_args = mock_gql.call_args
            input_data = call_args[0][1]["input"]
            assert input_data["projectId"] == "project-1"

    def test_create_issue_failure(self):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {
                "CLIENT_ID": "test-id",
                "CLIENT_SECRET": "test-secret",
            }
            service = LinearService()

        with patch.object(
            service, "_graphql", return_value={"issueCreate": {"success": False}}
        ):
            result = service.create_issue("Title", "Desc", "team-1")
            assert result is None

    def test_get_child_issues_maps_state_types(self):
        mock_response = {
            "issue": {
                "children": {
                    "nodes": [
                        {
                            "id": "id-1",
                            "identifier": "ENG-1",
                            "title": "Started task",
                            "url": "https://linear.app/t/ENG-1",
                            "state": {"type": "started"},
                            "assignee": None,
                        },
                        {
                            "id": "id-2",
                            "identifier": "ENG-2",
                            "title": "Done task",
                            "url": "https://linear.app/t/ENG-2",
                            "state": {"type": "completed"},
                            "assignee": {"id": "user-1", "email": "dev@example.com"},
                        },
                    ],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }

        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {
                "CLIENT_ID": "test-id",
                "CLIENT_SECRET": "test-secret",
            }
            service = LinearService()

        with patch.object(service, "_graphql", return_value=mock_response):
            issues = service.get_child_issues("parent-id")

            assert issues is not None
            assert len(issues) == 2
            assert issues[0]["status"] == "In Progress"
            assert issues[0]["relation_type"] == "child"
            assert issues[1]["status"] == "Done"
            assert issues[1]["assignee_email"] == "dev@example.com"

    def test_update_issue(self):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {
                "CLIENT_ID": "test-id",
                "CLIENT_SECRET": "test-secret",
            }
            service = LinearService()

        with patch.object(
            service, "_graphql", return_value={"issueUpdate": {"success": True}}
        ) as mock_gql:
            result = service.update_issue("issue-id", title="New title")

            assert result is True
            call_args = mock_gql.call_args
            assert call_args[0][1]["input"]["title"] == "New title"

    def test_get_workflow_states_caches(self):
        with patch("firetower.integrations.services.linear.settings") as mock_settings:
            mock_settings.LINEAR = {
                "CLIENT_ID": "test-id",
                "CLIENT_SECRET": "test-secret",
            }
            service = LinearService()

        mock_response = {
            "team": {
                "states": {
                    "nodes": [
                        {"id": "s1", "name": "Backlog", "type": "backlog"},
                        {"id": "s2", "name": "Todo", "type": "unstarted"},
                        {"id": "s3", "name": "In Progress", "type": "started"},
                        {"id": "s4", "name": "Done", "type": "completed"},
                        {"id": "s5", "name": "Canceled", "type": "canceled"},
                    ]
                }
            }
        }

        with patch.object(service, "_graphql", return_value=mock_response) as mock_gql:
            states = service.get_workflow_states("team-1")
            assert states["completed"] == "s4"
            assert states["backlog"] == "s1"

            states2 = service.get_workflow_states("team-1")
            assert states2 is states
            assert mock_gql.call_count == 1


@pytest.mark.django_db
class TestCreateLinearParentIssueHook:
    @patch("firetower.incidents.hooks._get_linear_service")
    @patch("firetower.incidents.hooks.settings")
    def test_claims_precreated_issue(self, mock_settings, mock_get_linear):
        mock_settings.LINEAR = {
            "TEAM_ID": "team-1",
            "PROJECT_ID": "",
            "SYNC_IDENTIFIERS": True,
        }
        mock_settings.FIRETOWER_BASE_URL = "https://firetower.example.com"

        mock_service = mock_get_linear.return_value
        mock_service.get_issue.return_value = {
            "id": "linear-issue-id",
            "identifier": "INC-100",
            "title": "Placeholder",
            "url": "https://linear.app/t/INC-100",
        }
        mock_service.get_workflow_states.return_value = {"started": "started-id"}
        mock_service.update_issue.return_value = True
        mock_service.create_attachment.return_value = True

        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        create_linear_parent_issue(incident)

        incident.refresh_from_db()
        assert incident.linear_parent_issue_id == "linear-issue-id"

        linear_link = ExternalLink.objects.get(
            incident=incident, type=ExternalLinkType.LINEAR
        )
        assert linear_link.url == "https://linear.app/t/INC-100"

        mock_service.create_issue.assert_not_called()
        mock_service.update_issue.assert_called_once()
        mock_service.create_attachment.assert_called_once_with(
            "linear-issue-id",
            f"https://firetower.example.com/{incident.incident_number}",
            f"Firetower: {incident.incident_number}",
        )

    @patch("firetower.incidents.hooks._get_linear_service")
    @patch("firetower.incidents.hooks.settings")
    def test_creates_placeholder_when_not_precreated(
        self, mock_settings, mock_get_linear
    ):
        mock_settings.LINEAR = {
            "TEAM_ID": "team-1",
            "PROJECT_ID": "",
            "SYNC_IDENTIFIERS": True,
        }
        mock_settings.FIRETOWER_BASE_URL = "https://firetower.example.com"

        mock_service = mock_get_linear.return_value
        issue_data = {
            "id": "linear-issue-id",
            "identifier": "INC-100",
            "title": "Placeholder",
            "url": "https://linear.app/t/INC-100",
        }
        mock_service.get_issue.side_effect = [None, issue_data]
        mock_service.create_issue.return_value = {
            "id": "placeholder-id",
            "identifier": "INC-99",
            "url": "https://linear.app/t/INC-99",
        }
        mock_service.get_workflow_states.return_value = {"started": "started-id"}
        mock_service.update_issue.return_value = True
        mock_service.create_attachment.return_value = True

        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        create_linear_parent_issue(incident)

        incident.refresh_from_db()
        assert incident.linear_parent_issue_id == "linear-issue-id"
        mock_service.create_issue.assert_called_once_with(
            "Placeholder", "", "team-1", None
        )

    @patch("firetower.incidents.hooks.settings")
    def test_skips_when_no_team_id(self, mock_settings):
        mock_settings.LINEAR = {"TEAM_ID": ""}

        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        create_linear_parent_issue(incident)

        assert not ExternalLink.objects.filter(
            incident=incident, type=ExternalLinkType.LINEAR
        ).exists()

    @patch("firetower.incidents.hooks._get_linear_service")
    @patch("firetower.incidents.hooks.settings")
    def test_cleans_up_on_claim_failure(self, mock_settings, mock_get_linear):
        mock_settings.LINEAR = {
            "TEAM_ID": "team-1",
            "PROJECT_ID": "",
            "SYNC_IDENTIFIERS": True,
        }
        mock_settings.FIRETOWER_BASE_URL = "https://firetower.example.com"

        mock_service = mock_get_linear.return_value
        mock_service.get_issue.return_value = None
        mock_service.create_issue.return_value = None

        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        create_linear_parent_issue(incident)

        assert not ExternalLink.objects.filter(
            incident=incident, type=ExternalLinkType.LINEAR
        ).exists()
        assert incident.linear_parent_issue_id is None

    @patch("firetower.incidents.hooks._get_linear_service")
    @patch("firetower.incidents.hooks.settings")
    def test_skips_when_link_already_exists(self, mock_settings, mock_get_linear):
        mock_settings.LINEAR = {"TEAM_ID": "team-1", "PROJECT_ID": ""}

        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            linear_parent_issue_id="existing-id",
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.LINEAR,
            url="https://linear.app/existing",
        )

        create_linear_parent_issue(incident)

        mock_get_linear.return_value.get_issue.assert_not_called()
        mock_get_linear.return_value.create_issue.assert_not_called()

    @patch("firetower.incidents.hooks._get_linear_service")
    @patch("firetower.incidents.hooks.settings")
    def test_creates_new_issue_when_sync_identifiers_disabled(
        self, mock_settings, mock_get_linear
    ):
        mock_settings.LINEAR = {
            "TEAM_ID": "team-1",
            "PROJECT_ID": "proj-1",
            "SYNC_IDENTIFIERS": False,
        }
        mock_settings.FIRETOWER_BASE_URL = "https://firetower.example.com"

        mock_service = mock_get_linear.return_value
        mock_service.create_issue.return_value = {
            "id": "new-issue-id",
            "identifier": "ENG-200",
            "url": "https://linear.app/t/ENG-200",
        }
        mock_service.create_attachment.return_value = True

        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        create_linear_parent_issue(incident)

        incident.refresh_from_db()
        assert incident.linear_parent_issue_id == "new-issue-id"

        linear_link = ExternalLink.objects.get(
            incident=incident, type=ExternalLinkType.LINEAR
        )
        assert linear_link.url == "https://linear.app/t/ENG-200"

        mock_service.get_issue.assert_not_called()
        mock_service.create_issue.assert_called_once()


@pytest.mark.django_db
class TestTitleChangeLinearSync:
    @patch("firetower.incidents.hooks._get_linear_service")
    def test_updates_linear_title(self, mock_get_linear, settings):
        settings.LINEAR = {"SYNC_IDENTIFIERS": False}
        mock_service = mock_get_linear.return_value
        mock_service.update_issue.return_value = True

        incident = Incident.objects.create(
            title="Updated Title",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            linear_parent_issue_id="linear-issue-id",
        )

        with patch("firetower.incidents.hooks._get_channel_id", return_value=None):
            on_title_changed(incident)

        mock_service.update_issue.assert_called_once_with(
            "linear-issue-id",
            title=f"[{incident.incident_number}] Updated Title",
        )

    @patch("firetower.incidents.hooks._get_linear_service")
    def test_skips_when_no_parent_issue(self, mock_get_linear, settings):
        settings.LINEAR = {"SYNC_IDENTIFIERS": False}
        incident = Incident.objects.create(
            title="Test",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        with patch("firetower.incidents.hooks._get_channel_id", return_value=None):
            on_title_changed(incident)

        mock_get_linear.return_value.update_issue.assert_not_called()

    @patch("firetower.incidents.hooks._get_linear_service")
    def test_redacts_title_for_private_incident(self, mock_get_linear, settings):
        settings.LINEAR = {"SYNC_IDENTIFIERS": False}
        mock_service = mock_get_linear.return_value
        mock_service.update_issue.return_value = True

        incident = Incident.objects.create(
            title="Secret Outage",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            linear_parent_issue_id="linear-issue-id",
            is_private=True,
        )

        with patch("firetower.incidents.hooks._get_channel_id", return_value=None):
            on_title_changed(incident)

        mock_service.update_issue.assert_called_once_with(
            "linear-issue-id",
            title=f"[{incident.incident_number}] Private Incident",
        )


@pytest.mark.django_db
class TestCreateLinearParentIssuePrivacy:
    @patch("firetower.incidents.hooks._get_linear_service")
    @patch("firetower.incidents.hooks.settings")
    def test_creates_with_redacted_title_for_private_incident(
        self, mock_settings, mock_get_linear
    ):
        mock_settings.LINEAR = {
            "TEAM_ID": "team-1",
            "PROJECT_ID": "",
            "SYNC_IDENTIFIERS": True,
        }
        mock_settings.FIRETOWER_BASE_URL = "https://firetower.example.com"

        mock_service = mock_get_linear.return_value
        mock_service.get_issue.return_value = {
            "id": "linear-issue-id",
            "identifier": "INC-100",
            "title": "Placeholder",
            "url": "https://linear.app/t/INC-100",
        }
        mock_service.get_workflow_states.return_value = {"started": "started-id"}
        mock_service.update_issue.return_value = True
        mock_service.create_attachment.return_value = True

        incident = Incident.objects.create(
            title="Secret Outage",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
        )

        create_linear_parent_issue(incident)

        call_args = mock_service.update_issue.call_args
        assert call_args[1]["title"] == "Private Incident"


@pytest.mark.django_db
class TestVisibilityChangeLinearSync:
    @patch("firetower.incidents.hooks._get_linear_service")
    def test_redacts_title_when_made_private(self, mock_get_linear, settings):
        settings.LINEAR = {"SYNC_IDENTIFIERS": False}
        mock_service = mock_get_linear.return_value
        mock_service.update_issue.return_value = True

        incident = Incident.objects.create(
            title="Visible Outage",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            linear_parent_issue_id="linear-issue-id",
            is_private=True,
        )

        with patch("firetower.incidents.hooks._get_channel_id", return_value=None):
            on_visibility_changed(incident)

        mock_service.update_issue.assert_called_once_with(
            "linear-issue-id",
            title=f"[{incident.incident_number}] Private Incident",
        )

    @patch("firetower.incidents.hooks._get_linear_service")
    def test_restores_title_when_made_public(self, mock_get_linear, settings):
        settings.LINEAR = {"SYNC_IDENTIFIERS": False}
        mock_service = mock_get_linear.return_value
        mock_service.update_issue.return_value = True

        incident = Incident.objects.create(
            title="Now Public Outage",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            linear_parent_issue_id="linear-issue-id",
            is_private=False,
        )

        with patch("firetower.incidents.hooks._get_channel_id", return_value=None):
            on_visibility_changed(incident)

        mock_service.update_issue.assert_called_once_with(
            "linear-issue-id",
            title=f"[{incident.incident_number}] Now Public Outage",
        )

    @patch("firetower.incidents.hooks._get_linear_service")
    def test_skips_when_no_parent_issue(self, mock_get_linear, settings):
        settings.LINEAR = {"SYNC_IDENTIFIERS": False}
        incident = Incident.objects.create(
            title="Test",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
        )

        with patch("firetower.incidents.hooks._get_channel_id", return_value=None):
            on_visibility_changed(incident)

        mock_get_linear.return_value.update_issue.assert_not_called()


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
        assert response.data[0]["relation_type"] == "child"
        assert response.data[0]["slo_deadline"] is None

    def test_list_action_items_includes_slo_deadline(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        ActionItem.objects.create(
            incident=incident,
            linear_issue_id="id-1",
            linear_identifier="ENG-1",
            title="High priority task",
            status=ActionItemStatus.TODO,
            priority=2,
            url="https://linear.app/t/ENG-1",
        )
        ActionItem.objects.create(
            incident=incident,
            linear_issue_id="id-2",
            linear_identifier="ENG-2",
            title="Medium priority task",
            status=ActionItemStatus.TODO,
            priority=3,
            url="https://linear.app/t/ENG-2",
        )
        ActionItem.objects.create(
            incident=incident,
            linear_issue_id="id-3",
            linear_identifier="ENG-3",
            title="Low priority task",
            status=ActionItemStatus.TODO,
            priority=4,
            url="https://linear.app/t/ENG-3",
        )

        linear_settings = {
            "ACTION_ITEM_SLO_DAYS_HIGH_PRIORITY": 14,
            "ACTION_ITEM_SLO_DAYS_MEDIUM_PRIORITY": 30,
        }

        with (
            override_settings(LINEAR=linear_settings),
            patch("firetower.incidents.views.sync_action_items_from_linear"),
        ):
            response = self.client.get(
                f"/api/ui/incidents/{incident.incident_number}/action-items/"
            )

        assert response.status_code == 200
        items = {item["linear_identifier"]: item for item in response.data}

        expected_high = (incident.created_at + timedelta(days=14)).isoformat()
        assert items["ENG-1"]["slo_deadline"] == expected_high

        expected_medium = (incident.created_at + timedelta(days=30)).isoformat()
        assert items["ENG-2"]["slo_deadline"] == expected_medium

        assert items["ENG-3"]["slo_deadline"] is None

    def test_list_action_items_no_slo_deadline_without_linear(self):
        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        ActionItem.objects.create(
            incident=incident,
            linear_issue_id="id-1",
            linear_identifier="ENG-1",
            title="High priority task",
            status=ActionItemStatus.TODO,
            priority=2,
            url="https://linear.app/t/ENG-1",
        )

        with patch("firetower.incidents.views.sync_action_items_from_linear"):
            response = self.client.get(
                f"/api/ui/incidents/{incident.incident_number}/action-items/"
            )

        assert response.status_code == 200
        assert response.data[0]["slo_deadline"] is None

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
