from unittest.mock import MagicMock, patch

import pytest

from firetower.incidents.models import IncidentSeverity, IncidentStatus
from firetower.slack_app.handlers.resolved import (
    handle_resolved_command,
    handle_resolved_submission,
)

from .conftest import CHANNEL_ID


@pytest.mark.django_db
class TestResolvedCommand:
    @patch("firetower.slack_app.bolt.get_bolt_app")
    def test_opens_modal(self, mock_get_bolt_app, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID, "trigger_id": "T12345"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_resolved_command(ack, body, command, respond)

        ack.assert_called_once()
        mock_get_bolt_app.return_value.client.views_open.assert_called_once()
        view = mock_get_bolt_app.return_value.client.views_open.call_args[1]["view"]
        assert view["callback_id"] == "resolved_incident_modal"

    def test_no_incident_responds_error(self, db):
        ack = MagicMock()
        body = {"channel_id": "C_UNKNOWN", "trigger_id": "T12345"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_resolved_command(ack, body, command, respond)

        ack.assert_called_once()
        assert "Could not find" in respond.call_args[0][0]


@pytest.mark.django_db
class TestResolvedSubmission:
    @patch("firetower.incidents.serializers.on_status_changed")
    @patch("firetower.incidents.serializers.on_severity_changed")
    @patch("firetower.incidents.serializers.on_captain_changed")
    @patch("firetower.incidents.serializers.on_title_changed")
    @patch("firetower.slack_app.handlers.resolved.get_or_create_user_from_slack_id")
    def test_p1_goes_to_postmortem(
        self,
        mock_get_user,
        mock_title_hook,
        mock_captain_hook,
        mock_sev_hook,
        mock_status_hook,
        user,
        incident,
    ):
        mock_get_user.return_value = user
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = {
            "private_metadata": CHANNEL_ID,
            "state": {
                "values": {
                    "severity_block": {
                        "severity_select": {"selected_option": {"value": "P1"}}
                    },
                    "captain_block": {"captain_select": {"selected_user": "U_CAPTAIN"}},
                }
            },
        }

        handle_resolved_submission(ack, body, view, client)

        ack.assert_called_once_with()
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.POSTMORTEM
        assert incident.severity == IncidentSeverity.P1
        client.chat_postMessage.assert_called_once()
        assert "Postmortem" in client.chat_postMessage.call_args[1]["text"]

    @patch("firetower.incidents.serializers.on_status_changed")
    @patch("firetower.incidents.serializers.on_title_changed")
    @patch("firetower.slack_app.handlers.resolved.get_or_create_user_from_slack_id")
    def test_p4_goes_to_done(
        self, mock_get_user, mock_title_hook, mock_status_hook, user, incident
    ):
        mock_get_user.return_value = user
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = {
            "private_metadata": CHANNEL_ID,
            "state": {
                "values": {
                    "severity_block": {
                        "severity_select": {"selected_option": {"value": "P4"}}
                    },
                    "captain_block": {"captain_select": {"selected_user": "U_CAPTAIN"}},
                }
            },
        }

        handle_resolved_submission(ack, body, view, client)

        ack.assert_called_once_with()
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.DONE

    def test_missing_captain_returns_error(self, incident):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = {
            "private_metadata": CHANNEL_ID,
            "state": {
                "values": {
                    "severity_block": {
                        "severity_select": {"selected_option": {"value": "P2"}}
                    },
                    "captain_block": {"captain_select": {"selected_user": None}},
                }
            },
        }

        handle_resolved_submission(ack, body, view, client)

        ack.assert_called_once()
        call_kwargs = ack.call_args[1]
        assert call_kwargs["response_action"] == "errors"
        assert "captain" in str(call_kwargs["errors"]).lower()
