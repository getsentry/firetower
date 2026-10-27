from unittest.mock import patch

import pytest
from django.contrib import messages
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory

from firetower.incidents.admin import IncidentAdmin
from firetower.incidents.models import Incident, IncidentSeverity, IncidentStatus
from firetower.incidents.services import (
    ActionItemLabelBackfillStats,
    ParticipantsSyncStats,
)


@pytest.mark.django_db
class TestIncidentAdmin:
    def setup_method(self):
        self.factory = RequestFactory()
        self.admin_user = User.objects.create_superuser(
            username="admin@example.com",
            email="admin@example.com",
            password="testpass123",
        )
        self.site = AdminSite()
        self.incident_admin = IncidentAdmin(Incident, self.site)

    def _add_session_and_messages(self, request):
        request.user = self.admin_user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_sync_participants_action_exists(self):
        request = self.factory.get("/")
        request = self._add_session_and_messages(request)
        actions = self.incident_admin.get_actions(request)
        assert "sync_participants_from_slack" in actions

    def test_action_label_actions_exist(self):
        request = self._add_session_and_messages(self.factory.get("/"))
        actions = self.incident_admin.get_actions(request)
        assert "preview_action_item_labels" in actions
        assert "backfill_action_item_labels" in actions

    def test_action_label_actions_require_change_permission(self):
        request = self._add_session_and_messages(self.factory.get("/"))
        request.user = User.objects.create_user(username="read-only", is_staff=True)
        actions = self.incident_admin.get_actions(request)
        assert "preview_action_item_labels" not in actions
        assert "backfill_action_item_labels" not in actions

    @pytest.mark.parametrize(
        ("action", "dry_run"),
        [("preview_action_item_labels", True), ("backfill_action_item_labels", False)],
    )
    def test_action_label_admin_post_limits_backfill_to_selection(
        self, client, action, dry_run
    ):
        selected = Incident.objects.create(
            title="Selected", severity=IncidentSeverity.P2
        )
        Incident.objects.create(title="Not selected", severity=IncidentSeverity.P2)
        client.force_login(self.admin_user)

        with patch("firetower.incidents.admin.backfill_action_item_labels") as backfill:
            backfill.return_value = ActionItemLabelBackfillStats()
            response = client.post(
                "/admin/incidents/incident/",
                {"action": action, "_selected_action": [str(selected.pk)]},
            )

        assert response.status_code == 302
        backfill.assert_called_once()
        assert list(backfill.call_args.args[0]) == [selected]
        assert backfill.call_args.kwargs == {"dry_run": dry_run}

    @pytest.mark.parametrize(
        ("action", "dry_run"),
        [("preview_action_item_labels", True), ("backfill_action_item_labels", False)],
    )
    def test_action_label_actions_report_counts(self, action, dry_run):
        request = self._add_session_and_messages(self.factory.post("/"))
        queryset = Incident.objects.none()
        with (
            patch("firetower.incidents.admin.backfill_action_item_labels") as backfill,
            patch.object(self.incident_admin, "message_user") as message_user,
        ):
            backfill.return_value = ActionItemLabelBackfillStats(
                checked=3, missing=2, added=0 if dry_run else 2
            )
            getattr(self.incident_admin, action)(request, queryset)

        backfill.assert_called_once_with(queryset, dry_run=dry_run)
        message = message_user.call_args.args[1]
        assert "3 checked" in message
        assert "2 missing labels" in message
        assert f"{0 if dry_run else 2} added" in message
        assert "0 failures" in message
        assert message_user.call_args.kwargs["level"] == messages.SUCCESS

    def test_action_label_backfill_reports_partial_failure(self):
        request = self._add_session_and_messages(self.factory.post("/"))
        with (
            patch("firetower.incidents.admin.backfill_action_item_labels") as backfill,
            patch.object(self.incident_admin, "message_user") as message_user,
        ):
            backfill.return_value = ActionItemLabelBackfillStats(
                checked=3,
                missing=2,
                added=1,
                errors=["Failed to label action item ENG-1"],
            )
            self.incident_admin.backfill_action_item_labels(
                request, Incident.objects.none()
            )

        message = message_user.call_args.args[1]
        assert "1 added" in message
        assert "1 failures" in message
        assert "Failed to label action item ENG-1" in message
        assert message_user.call_args.kwargs["level"] == messages.ERROR

    def test_action_label_backfill_reports_missing_configuration(self):
        request = self._add_session_and_messages(self.factory.post("/"))
        with patch.object(self.incident_admin, "message_user") as message_user:
            self.incident_admin.backfill_action_item_labels(
                request, Incident.objects.none()
            )
        assert "Linear integration is not configured" in message_user.call_args.args[1]
        assert message_user.call_args.kwargs["level"] == messages.ERROR

    def test_sync_participants_action_calls_sync_function(self):
        incident1 = Incident.objects.create(
            title="Test Incident 1",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        incident2 = Incident.objects.create(
            title="Test Incident 2",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P2,
        )

        request = self.factory.get("/admin/incidents/incident/")
        request = self._add_session_and_messages(request)

        queryset = Incident.objects.filter(id__in=[incident1.id, incident2.id])

        with patch(
            "firetower.incidents.admin.sync_incident_participants_from_slack"
        ) as mock_sync:
            mock_sync.return_value = ParticipantsSyncStats(
                added=5,
                already_existed=2,
            )

            self.incident_admin.sync_participants_from_slack(request, queryset)

            assert mock_sync.call_count == 2
            mock_sync.assert_any_call(incident1, force=True)
            mock_sync.assert_any_call(incident2, force=True)

    def test_sync_participants_action_reports_stats(self):
        incident1 = Incident.objects.create(
            title="Success",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        incident2 = Incident.objects.create(
            title="With Errors",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P2,
        )
        incident3 = Incident.objects.create(
            title="Exception",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P3,
        )

        request = self.factory.get("/admin/incidents/incident/")
        request = self._add_session_and_messages(request)

        queryset = Incident.objects.filter(
            id__in=[incident1.id, incident2.id, incident3.id]
        )

        with patch(
            "firetower.incidents.admin.sync_incident_participants_from_slack"
        ) as mock_sync:

            def side_effect(incident, force):
                if incident.id == incident1.id:
                    return ParticipantsSyncStats(
                        added=5,
                        already_existed=2,
                    )
                elif incident.id == incident2.id:
                    return ParticipantsSyncStats(
                        errors=["Some error"],
                    )
                else:
                    raise Exception("Sync failed")

            mock_sync.side_effect = side_effect

            with patch.object(self.incident_admin, "message_user") as mock_message:
                self.incident_admin.sync_participants_from_slack(request, queryset)

                mock_message.assert_called_once()
                message = mock_message.call_args[0][1]
                assert "1 synced successfully" in message
                assert "2 failed" in message
