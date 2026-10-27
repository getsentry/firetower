import runpy
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
from django.utils import timezone

from firetower.incidents.models import (
    ActionItem,
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from firetower.incidents.services import (
    backfill_action_item_labels,
    sync_action_items_from_linear,
)
from firetower.integrations.services.linear import LinearRateLimitError, LinearService

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


@pytest.fixture
def backfill_main():
    script = (
        Path(__file__).resolve().parents[4]
        / "scripts/backfill_incident_action_labels.py"
    )
    with patch("django.setup"):
        yield runpy.run_path(str(script))["main"]


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


class TestBackfillActionItemLabels:
    def test_stops_on_rate_limited_label_lookup(self, service):
        service.get_issue_label_id.side_effect = LinearRateLimitError("60")
        stats = backfill_action_item_labels(Incident.objects.all(), dry_run=False)
        assert stats.added == 0
        assert "Retry after 60 seconds" in stats.errors[0]
        assert "Backfill stopped" in stats.errors[0]
        service.get_issue_label_id.assert_called_once_with(
            "incident-action", raise_on_error=True
        )
        service.get_child_issues.assert_not_called()
        service.add_issue_label.assert_not_called()

    @pytest.mark.parametrize("dry_run", [False, True])
    def test_stops_on_rate_limited_child_fetch(self, incident, issue, service, dry_run):
        for parent_id in ("parent-2", "parent-3"):
            Incident.objects.create(
                title=parent_id,
                severity=IncidentSeverity.P2,
                linear_parent_issue_id=parent_id,
            )
        service.get_child_issues.side_effect = [[issue], LinearRateLimitError("60"), []]
        stats = backfill_action_item_labels(
            Incident.objects.order_by("id"), dry_run=dry_run
        )
        assert stats.checked == stats.missing == 1
        assert stats.added == (0 if dry_run else 1)
        assert "Backfill stopped" in stats.errors[0]
        assert service.get_child_issues.call_count == 2
        assert service.add_issue_label.call_count == (0 if dry_run else 1)

    def test_stops_labeling_on_rate_limit_and_rerun_skips_completed_items(
        self, incident, issue, service
    ):
        Incident.objects.create(
            title="Another incident",
            severity=IncidentSeverity.P2,
            linear_parent_issue_id="parent-2",
        )
        children = [
            issue,
            {**issue, "id": "issue-2", "identifier": "ENG-2", "label_ids": []},
            {**issue, "id": "issue-3", "identifier": "ENG-3", "label_ids": []},
        ]
        service.get_child_issues.return_value = children
        service.add_issue_label.side_effect = [True, LinearRateLimitError("90"), True]
        stats = backfill_action_item_labels(
            Incident.objects.order_by("id"), dry_run=False
        )
        assert stats.checked == stats.missing == 2
        assert stats.added == 1
        assert "Retry after 90 seconds" in stats.errors[0]
        assert "Backfill stopped" in stats.errors[0]
        assert service.add_issue_label.call_count == 2
        service.get_child_issues.assert_called_once_with(
            "parent-1", include_archived=True, raise_on_error=True
        )

        issue["label_ids"].append("action-label")
        service.add_issue_label.side_effect = None
        service.add_issue_label.reset_mock()
        stats = backfill_action_item_labels(Incident.objects.all(), dry_run=False)
        assert stats.checked == 3
        assert stats.missing == stats.added == 2
        assert stats.errors == []
        service.add_issue_label.assert_has_calls(
            [
                call("issue-2", "action-label", raise_on_error=True),
                call("issue-3", "action-label", raise_on_error=True),
            ]
        )
        assert service.add_issue_label.call_count == 2

    def test_rate_limit_message_takes_precedence_over_earlier_failures(
        self, incident, issue, service
    ):
        service.get_child_issues.return_value = [
            issue,
            {**issue, "id": "issue-2", "identifier": "ENG-2"},
        ]
        service.add_issue_label.side_effect = [False, LinearRateLimitError("60")]
        stats = backfill_action_item_labels(Incident.objects.all(), dry_run=False)
        assert len(stats.errors) == 2
        assert "Backfill stopped" in stats.errors[0]
        assert stats.errors[1] == "Failed to label action item ENG-1"

    def test_respects_selected_incidents(self, incident, service):
        Incident.objects.create(
            title="Not selected",
            severity=IncidentSeverity.P2,
            linear_parent_issue_id="parent-2",
        )
        stats = backfill_action_item_labels(
            Incident.objects.filter(pk=incident.pk), dry_run=False
        )
        assert stats.checked == stats.missing == stats.added == 1
        assert stats.errors == []
        service.get_child_issues.assert_called_once_with(
            "parent-1", include_archived=True, raise_on_error=True
        )

    def test_preview_reports_counts_without_adding_labels(
        self, incident, issue, service
    ):
        service.get_child_issues.return_value = [
            issue,
            {**issue, "id": "issue-2", "label_ids": ["action-label"]},
        ]
        stats = backfill_action_item_labels(Incident.objects.all())
        assert stats.checked == 2
        assert stats.missing == 1
        assert stats.added == 0
        assert stats.errors == []
        service.add_issue_label.assert_not_called()

    def test_continues_after_unexpected_child_fetch_error(self, incident, service):
        Incident.objects.create(
            title="Another incident",
            severity=IncidentSeverity.P2,
            linear_parent_issue_id="parent-2",
        )
        service.get_child_issues.side_effect = [
            RuntimeError("Fetch failed"),
            service.get_child_issues.return_value,
        ]
        stats = backfill_action_item_labels(Incident.objects.all(), dry_run=False)
        assert stats.checked == stats.added == 1
        assert len(stats.errors) == 1
        assert service.get_child_issues.call_count == 2

    def test_continues_after_unexpected_label_error(self, incident, issue, service):
        service.get_child_issues.return_value = [
            issue,
            {**issue, "id": "issue-2", "identifier": "ENG-2"},
        ]
        service.add_issue_label.side_effect = [RuntimeError("Update failed"), True]
        stats = backfill_action_item_labels(Incident.objects.all(), dry_run=False)
        assert stats.checked == stats.missing == 2
        assert stats.added == 1
        assert stats.errors == ["Failed to label action item ENG-1"]

    def test_reports_label_lookup_exception(self, service):
        service.get_issue_label_id.side_effect = RuntimeError("Lookup failed")
        stats = backfill_action_item_labels(Incident.objects.all(), dry_run=False)
        assert stats.errors == ["Failed to fetch Linear incident action label"]
        service.get_child_issues.assert_not_called()
        service.add_issue_label.assert_not_called()

    def test_reports_missing_configuration(self, settings, service):
        settings.LINEAR = None
        stats = backfill_action_item_labels(Incident.objects.all(), dry_run=False)
        assert stats.errors == ["Linear integration is not configured"]
        service.get_issue_label_id.assert_not_called()

    def test_dry_run_does_not_mutate_issues_or_cached_items(
        self, incident, service, backfill_main
    ):
        assert backfill_main([]) == 0
        service.get_child_issues.assert_called_once_with(
            "parent-1", include_archived=True, raise_on_error=True
        )
        service.add_issue_label.assert_not_called()
        service.update_issue.assert_not_called()
        service.create_comment.assert_not_called()
        assert incident.action_items.count() == 0

    def test_apply_skips_existing_labels(self, incident, issue, service, backfill_main):
        service.get_child_issues.return_value = [
            issue,
            {
                **issue,
                "id": "issue-2",
                "identifier": "ENG-2",
                "label_ids": ["action-label"],
            },
        ]
        assert backfill_main(["--apply"]) == 0
        service.add_issue_label.assert_called_once_with(
            "issue-1", "action-label", raise_on_error=True
        )
        service.update_issue.assert_not_called()
        assert incident.action_items.count() == 0

        issue["label_ids"].append("action-label")
        assert backfill_main(["--apply"]) == 0
        service.add_issue_label.assert_called_once_with(
            "issue-1", "action-label", raise_on_error=True
        )

    def test_includes_historical_private_incidents_and_deduplicates(
        self, incident, issue, service, backfill_main
    ):
        old_incident = Incident.objects.create(
            title="Old private incident",
            severity=IncidentSeverity.P4,
            status=IncidentStatus.CANCELED,
            is_private=True,
            linear_parent_issue_id="parent-2",
        )
        Incident.objects.filter(pk=old_incident.pk).update(
            created_at=timezone.now() - timedelta(days=365)
        )
        Incident.objects.create(title="No Linear parent", severity=IncidentSeverity.P2)
        Incident.objects.create(
            title="Empty Linear parent",
            severity=IncidentSeverity.P2,
            linear_parent_issue_id="",
        )

        assert backfill_main(["--apply"]) == 0

        service.get_child_issues.assert_has_calls(
            [
                call("parent-1", include_archived=True, raise_on_error=True),
                call("parent-2", include_archived=True, raise_on_error=True),
            ],
            any_order=True,
        )
        assert service.get_child_issues.call_count == 2
        service.add_issue_label.assert_called_once_with(
            "issue-1", "action-label", raise_on_error=True
        )

    def test_reports_failed_additions(self, incident, service, backfill_main):
        service.add_issue_label.return_value = False
        assert backfill_main(["--apply"]) == 1

    def test_reports_incomplete_fetch_and_continues(
        self, incident, service, backfill_main
    ):
        Incident.objects.create(
            title="Another incident",
            severity=IncidentSeverity.P2,
            linear_parent_issue_id="parent-2",
        )
        service.get_child_issues.side_effect = [
            None,
            service.get_child_issues.return_value,
        ]
        assert backfill_main(["--apply"]) == 1
        assert service.get_child_issues.call_count == 2
        service.add_issue_label.assert_called_once_with(
            "issue-1", "action-label", raise_on_error=True
        )

    def test_stops_when_label_is_missing(self, service, backfill_main):
        service.get_issue_label_id.return_value = None
        assert backfill_main(["--apply"]) == 1
        service.get_child_issues.assert_not_called()
        service.add_issue_label.assert_not_called()

    def test_requires_linear_configuration(self, settings, backfill_main):
        settings.LINEAR = None
        with pytest.raises(SystemExit) as error:
            backfill_main([])
        assert error.value.code == 2
