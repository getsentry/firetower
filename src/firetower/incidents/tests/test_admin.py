from unittest.mock import patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory

from firetower.incidents.admin import IncidentAdmin
from firetower.incidents.models import Incident, IncidentSeverity, IncidentStatus


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
            mock_sync.return_value = {
                "added": 5,
                "already_existed": 2,
                "errors": [],
                "skipped": False,
            }

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
                    return {
                        "added": 5,
                        "already_existed": 2,
                        "errors": [],
                        "skipped": False,
                    }
                elif incident.id == incident2.id:
                    return {
                        "added": 0,
                        "already_existed": 0,
                        "errors": ["Some error"],
                        "skipped": False,
                    }
                else:
                    raise Exception("Sync failed")

            mock_sync.side_effect = side_effect

            with patch.object(self.incident_admin, "message_user") as mock_message:
                self.incident_admin.sync_participants_from_slack(request, queryset)

                mock_message.assert_called_once()
                message = mock_message.call_args[0][1]
                assert "1 synced successfully" in message
                assert "2 failed" in message
