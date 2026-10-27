from datetime import timedelta
from unittest.mock import MagicMock, call, patch

import pytest
from django.utils import timezone

from firetower.incidents.models import (
    ActionItem,
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from firetower.incidents.services import sync_action_items_from_linear
from firetower.integrations.services.linear import LinearService

pytestmark = pytest.mark.django_db


@pytest.fixture
def issue():
    return {
        "id": "issue-1",
        "identifier": "ENG-1",
        "title": "Pre-existing follow-up",
        "url": "https://linear.app/issue/ENG-1",
        "status": "Todo",
        "priority": 0,
        "relation_type": "child",
        "created_at": timezone.now() - timedelta(days=365),
        "label_ids": ["unrelated-label"],
    }


@pytest.fixture
def service(settings, issue):
    settings.LINEAR = {"TEAM_ID": "incident-team"}
    service = MagicMock(spec=LinearService)
    service.get_child_issues.return_value = [issue]
    service.get_issue_label_id.return_value = "action-label"
    service.add_issue_label.return_value = True
    with patch(
        "firetower.incidents.services._get_linear_service", return_value=service
    ):
        yield service


@pytest.fixture
def incident():
    return Incident.objects.create(
        title="Incident",
        severity=IncidentSeverity.P2,
        status=IncidentStatus.POSTMORTEM,
        linear_parent_issue_id="parent-1",
    )


class TestActionItemLabels:
    @pytest.mark.parametrize("already_synced", [False, True])
    def test_labels_newly_adopted_and_cached_items(
        self, incident, issue, service, already_synced
    ):
        if already_synced:
            ActionItem.objects.create(
                incident=incident,
                linear_issue_id=issue["id"],
                linear_identifier=issue["identifier"],
                title="Old title",
                url=issue["url"],
            )

        stats = sync_action_items_from_linear(incident, force=True)

        assert stats.errors == []
        item = incident.action_items.get()
        assert item.created_at == issue["created_at"]
        service.add_issue_label.assert_called_once_with("issue-1", "action-label")
        service.get_issue_label_id.assert_called_once_with("incident-action")

    @pytest.mark.parametrize("severity", IncidentSeverity.values)
    @pytest.mark.parametrize("status", ["Todo", "In Progress", "Done", "Canceled"])
    def test_labels_every_severity_and_action_status(
        self, incident, issue, service, severity, status
    ):
        incident.severity = severity
        issue["status"] = status
        sync_action_items_from_linear(incident, force=True)
        service.add_issue_label.assert_called_once_with("issue-1", "action-label")

    def test_skips_already_labeled_items(self, incident, issue, service):
        issue["label_ids"].append("action-label")
        stats = sync_action_items_from_linear(incident, force=True)
        assert stats.created == 1
        assert stats.errors == []
        service.add_issue_label.assert_not_called()

    @pytest.mark.parametrize("failure", [False, RuntimeError("Label update failed")])
    def test_label_failure_does_not_block_sync_or_other_items(
        self, incident, issue, service, failure
    ):
        service.get_child_issues.return_value = [
            issue,
            {**issue, "id": "issue-2", "identifier": "ENG-2"},
        ]
        service.add_issue_label.side_effect = [failure, True]

        stats = sync_action_items_from_linear(incident, force=True)

        assert stats.created == 2
        assert stats.errors == ["Failed to label action item ENG-1"]
        assert incident.action_items.count() == 2
        service.add_issue_label.assert_has_calls(
            [call("issue-1", "action-label"), call("issue-2", "action-label")]
        )

        service.add_issue_label.side_effect = None
        stats = sync_action_items_from_linear(incident, force=True)
        assert stats.errors == []
        assert stats.updated == 2

    @pytest.mark.parametrize("failure", [None, RuntimeError("Label lookup failed")])
    def test_missing_label_does_not_block_sync(self, incident, service, failure):
        if isinstance(failure, Exception):
            service.get_issue_label_id.side_effect = failure
        else:
            service.get_issue_label_id.return_value = failure

        stats = sync_action_items_from_linear(incident, force=True)

        assert stats.created == 1
        assert len(stats.errors) == 1
        service.add_issue_label.assert_not_called()

    def test_does_not_fetch_label_without_children(self, incident, service):
        service.get_child_issues.return_value = []
        sync_action_items_from_linear(incident, force=True)
        service.get_issue_label_id.assert_not_called()
        service.add_issue_label.assert_not_called()
