from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from firetower.auth.models import ExternalProfile, ExternalProfileType, UserProfile
from firetower.incidents.hooks import _create_linear_parent_issue, on_title_changed
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
            mock_get.return_value.get_related_issues.return_value = []
            mock_get.return_value.get_workflow_states.return_value = None

            stats = sync_action_items_from_linear(incident, force=True)

            assert stats.created == 2
            assert stats.updated == 0
            assert stats.deleted == 0
            assert incident.action_items.count() == 2
            assert incident.action_items_last_synced_at is not None

    def test_creates_action_items_from_relations(self):
        incident = self._make_incident()

        related = [
            _make_linear_issue(
                id="id-r1",
                identifier="ENG-10",
                title="Related task",
                relation_type="related",
            ),
            _make_linear_issue(
                id="id-r2",
                identifier="ENG-11",
                title="Blocking task",
                relation_type="blocks",
            ),
        ]

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_get.return_value.get_child_issues.return_value = []
            mock_get.return_value.get_related_issues.return_value = related
            mock_get.return_value.get_workflow_states.return_value = None

            stats = sync_action_items_from_linear(incident, force=True)

            assert stats.created == 2
            item_r1 = incident.action_items.get(linear_issue_id="id-r1")
            assert item_r1.relation_type == ActionItemRelationType.RELATED
            item_r2 = incident.action_items.get(linear_issue_id="id-r2")
            assert item_r2.relation_type == ActionItemRelationType.BLOCKS

    def test_combines_children_and_relations(self):
        incident = self._make_incident()

        children = [
            _make_linear_issue(id="id-1", identifier="ENG-1", title="Child task"),
        ]
        related = [
            _make_linear_issue(
                id="id-2",
                identifier="ENG-2",
                title="Related task",
                relation_type="related",
            ),
        ]

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_get.return_value.get_child_issues.return_value = children
            mock_get.return_value.get_related_issues.return_value = related
            mock_get.return_value.get_workflow_states.return_value = None

            stats = sync_action_items_from_linear(incident, force=True)

            assert stats.created == 2
            assert incident.action_items.count() == 2

    def test_deduplicates_children_and_relations(self):
        incident = self._make_incident()

        children = [
            _make_linear_issue(id="id-1", identifier="ENG-1", title="Task"),
        ]
        related = [
            _make_linear_issue(
                id="id-1",
                identifier="ENG-1",
                title="Task",
                relation_type="related",
            ),
        ]

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_get.return_value.get_child_issues.return_value = children
            mock_get.return_value.get_related_issues.return_value = related
            mock_get.return_value.get_workflow_states.return_value = None

            stats = sync_action_items_from_linear(incident, force=True)

            assert stats.created == 1
            item = incident.action_items.get(linear_issue_id="id-1")
            assert item.relation_type == ActionItemRelationType.CHILD

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
            mock_get.return_value.get_related_issues.return_value = []
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
            mock_get.return_value.get_related_issues.return_value = []
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
            mock_get.return_value.get_related_issues.return_value = []
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

    def test_handles_relations_api_failure(self):
        incident = self._make_incident()

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_get.return_value.get_child_issues.return_value = []
            mock_get.return_value.get_related_issues.return_value = None

            stats = sync_action_items_from_linear(incident, force=True)

            assert len(stats.errors) == 1
            assert "related issues" in stats.errors[0]
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
            mock_get.return_value.get_related_issues.return_value = []
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
            mock_get.return_value.get_related_issues.return_value = []
            mock_get.return_value.get_workflow_states.return_value = None

            sync_action_items_from_linear(incident, force=True)

            item = incident.action_items.get(linear_issue_id="id-1")
            assert item.assignee is not None
            assert item.assignee.email == "newdev@example.com"
            profile = ExternalProfile.objects.get(
                user=item.assignee, type=ExternalProfileType.LINEAR
            )
            assert profile.external_id == "linear-user-456"

    def test_auto_completes_parent_when_all_done(self, settings):
        settings.LINEAR = {"TEAM_ID": "team-1"}
        incident = self._make_incident()

        children = [
            _make_linear_issue(
                id="id-1", identifier="ENG-1", title="T1", status="Done"
            ),
            _make_linear_issue(
                id="id-2", identifier="ENG-2", title="T2", status="Cancelled"
            ),
        ]

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_service = mock_get.return_value
            mock_service.get_child_issues.return_value = children
            mock_service.get_related_issues.return_value = []
            mock_service.get_workflow_states.return_value = {
                "completed": "state-done",
                "backlog": "state-backlog",
            }
            mock_service.update_issue.return_value = True

            sync_action_items_from_linear(incident, force=True)

            mock_service.update_issue.assert_called_once_with(
                "parent-issue-id", state_id="state-done"
            )

    def test_does_not_reopen_parent_when_incomplete_items(self, settings):
        settings.LINEAR = {"TEAM_ID": "team-1"}
        incident = self._make_incident()

        children = [
            _make_linear_issue(
                id="id-1", identifier="ENG-1", title="T1", status="Done"
            ),
            _make_linear_issue(
                id="id-2", identifier="ENG-2", title="T2", status="Todo"
            ),
        ]

        with patch("firetower.incidents.services._get_linear_service") as mock_get:
            mock_service = mock_get.return_value
            mock_service.get_child_issues.return_value = children
            mock_service.get_related_issues.return_value = []
            mock_service.get_workflow_states.return_value = {
                "completed": "state-done",
                "backlog": "state-backlog",
            }

            sync_action_items_from_linear(incident, force=True)

            mock_service.update_issue.assert_not_called()


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

    def test_get_related_issues_maps_relation_types(self):
        mock_response = {
            "issue": {
                "relations": {
                    "nodes": [
                        {
                            "type": "related",
                            "relatedIssue": {
                                "id": "id-1",
                                "identifier": "ENG-1",
                                "title": "Related task",
                                "url": "https://linear.app/t/ENG-1",
                                "state": {"type": "unstarted"},
                                "assignee": None,
                            },
                        },
                        {
                            "type": "blocks",
                            "relatedIssue": {
                                "id": "id-2",
                                "identifier": "ENG-2",
                                "title": "Blocking task",
                                "url": "https://linear.app/t/ENG-2",
                                "state": {"type": "started"},
                                "assignee": None,
                            },
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
            issues = service.get_related_issues("parent-id")

            assert issues is not None
            assert len(issues) == 2
            assert issues[0]["relation_type"] == "related"
            assert issues[1]["relation_type"] == "blocks"

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
                        {"id": "s5", "name": "Cancelled", "type": "cancelled"},
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
    @patch("firetower.incidents.hooks.LinearService")
    @patch("firetower.incidents.hooks.settings")
    def test_creates_parent_issue_and_attachment(
        self, mock_settings, MockLinearService
    ):
        mock_settings.LINEAR = {"TEAM_ID": "team-1", "PROJECT_ID": ""}
        mock_settings.FIRETOWER_BASE_URL = "https://firetower.example.com"

        mock_service = MockLinearService.return_value
        mock_service.create_issue.return_value = {
            "id": "linear-issue-id",
            "identifier": "ENG-100",
            "url": "https://linear.app/t/ENG-100",
        }
        mock_service.create_attachment.return_value = True

        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        _create_linear_parent_issue(incident)

        incident.refresh_from_db()
        assert incident.linear_parent_issue_id == "linear-issue-id"

        linear_link = ExternalLink.objects.get(
            incident=incident, type=ExternalLinkType.LINEAR
        )
        assert linear_link.url == "https://linear.app/t/ENG-100"

        mock_service.create_attachment.assert_called_once_with(
            "linear-issue-id",
            f"https://firetower.example.com/{incident.incident_number}",
            f"Firetower: {incident.incident_number}",
        )

    @patch("firetower.incidents.hooks.settings")
    def test_skips_when_no_team_id(self, mock_settings):
        mock_settings.LINEAR = {"TEAM_ID": ""}

        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        _create_linear_parent_issue(incident)

        assert not ExternalLink.objects.filter(
            incident=incident, type=ExternalLinkType.LINEAR
        ).exists()

    @patch("firetower.incidents.hooks.LinearService")
    @patch("firetower.incidents.hooks.settings")
    def test_cleans_up_on_failure(self, mock_settings, MockLinearService):
        mock_settings.LINEAR = {"TEAM_ID": "team-1", "PROJECT_ID": ""}
        mock_settings.FIRETOWER_BASE_URL = "https://firetower.example.com"

        mock_service = MockLinearService.return_value
        mock_service.create_issue.return_value = None

        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        _create_linear_parent_issue(incident)

        assert not ExternalLink.objects.filter(
            incident=incident, type=ExternalLinkType.LINEAR
        ).exists()
        assert incident.linear_parent_issue_id is None

    @patch("firetower.incidents.hooks.LinearService")
    @patch("firetower.incidents.hooks.settings")
    def test_skips_when_link_already_exists(self, mock_settings, MockLinearService):
        mock_settings.LINEAR = {"TEAM_ID": "team-1", "PROJECT_ID": ""}

        incident = Incident.objects.create(
            title="Test Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.LINEAR,
            url="https://linear.app/existing",
        )

        _create_linear_parent_issue(incident)

        MockLinearService.return_value.create_issue.assert_not_called()


@pytest.mark.django_db
class TestTitleChangeLinearSync:
    @patch("firetower.incidents.hooks.LinearService")
    def test_updates_linear_title(self, MockLinearService):
        mock_service = MockLinearService.return_value
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

    @patch("firetower.incidents.hooks.LinearService")
    def test_skips_when_no_parent_issue(self, MockLinearService):
        incident = Incident.objects.create(
            title="Test",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        with patch("firetower.incidents.hooks._get_channel_id", return_value=None):
            on_title_changed(incident)

        MockLinearService.return_value.update_issue.assert_not_called()


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
