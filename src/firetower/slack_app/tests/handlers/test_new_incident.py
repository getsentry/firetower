from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.incidents.models import Incident, IncidentSeverity
from firetower.slack_app.bolt import handle_command
from firetower.slack_app.handlers.new_incident import (
    handle_new_command,
    handle_new_incident_submission,
)


class TestNewSubcommandRouting:
    def _make_body(self, text="", command="/ft"):
        return {"text": text, "command": command}

    def _make_command(self, command="/ft", text=""):
        return {"command": command, "text": text}

    @patch("firetower.slack_app.bolt._bolt_app")
    @patch("firetower.slack_app.bolt.statsd")
    def test_new_subcommand_routes_correctly(self, mock_statsd, mock_bolt_app):
        ack = MagicMock()
        respond = MagicMock()
        body = self._make_body(text="new")
        body["trigger_id"] = "T12345"
        command = self._make_command()

        handle_command(ack=ack, body=body, command=command, respond=respond)

        ack.assert_called_once()
        mock_bolt_app.client.views_open.assert_called_once()


@pytest.mark.django_db
class TestNewIncidentModal:
    @patch("firetower.slack_app.bolt._bolt_app")
    def test_new_opens_modal(self, mock_bolt_app):
        ack = MagicMock()
        body = {"trigger_id": "T12345"}
        command = {"text": "new"}
        respond = MagicMock()

        handle_new_command(ack, body, command, respond)

        ack.assert_called_once()
        mock_bolt_app.client.views_open.assert_called_once()
        view = mock_bolt_app.client.views_open.call_args[1]["view"]
        assert view["callback_id"] == "new_incident_modal"
        assert view["type"] == "modal"


@pytest.mark.django_db
class TestNewIncidentSubmission:
    def setup_method(self):
        self.user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )
        ExternalProfile.objects.create(
            user=self.user,
            type=ExternalProfileType.SLACK,
            external_id="U_TEST",
        )

    @patch("firetower.incidents.serializers.on_incident_created")
    @patch("firetower.slack_app.handlers.new_incident.get_or_create_user_from_slack_id")
    def test_creates_incident(self, mock_get_user, mock_hook):
        mock_get_user.return_value = self.user

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_TEST"}}
        view = {
            "state": {
                "values": {
                    "title_block": {"title": {"value": "Test Incident"}},
                    "severity_block": {
                        "severity": {
                            "selected_option": {"value": "P1"},
                        }
                    },
                    "description_block": {"description": {"value": "Description"}},
                    "private_block": {"is_private": {"selected_options": []}},
                }
            }
        }

        handle_new_incident_submission(ack, body, view, client)

        ack.assert_called_once_with()
        incident = Incident.objects.get(title="Test Incident")
        assert incident.severity == IncidentSeverity.P1
        assert incident.captain == self.user
        assert incident.reporter == self.user
        client.chat_postMessage.assert_called_once()

    @patch("firetower.slack_app.handlers.new_incident.get_or_create_user_from_slack_id")
    def test_validation_error(self, mock_get_user):
        mock_get_user.return_value = self.user

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_TEST"}}
        view = {
            "state": {
                "values": {
                    "title_block": {"title": {"value": ""}},
                    "severity_block": {
                        "severity": {
                            "selected_option": {"value": "P1"},
                        }
                    },
                    "description_block": {"description": {"value": ""}},
                    "private_block": {"is_private": {"selected_options": []}},
                }
            }
        }

        handle_new_incident_submission(ack, body, view, client)

        ack.assert_called_once()
        call_kwargs = ack.call_args[1]
        assert call_kwargs["response_action"] == "errors"
        client.chat_postMessage.assert_not_called()

    @patch("firetower.slack_app.handlers.new_incident.get_or_create_user_from_slack_id")
    def test_unknown_user_returns_error(self, mock_get_user):
        mock_get_user.return_value = None

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_UNKNOWN"}}
        view = {
            "state": {
                "values": {
                    "title_block": {"title": {"value": "Test"}},
                    "severity_block": {
                        "severity": {"selected_option": {"value": "P1"}}
                    },
                    "description_block": {"description": {"value": ""}},
                    "private_block": {"is_private": {"selected_options": []}},
                }
            }
        }

        handle_new_incident_submission(ack, body, view, client)

        ack.assert_called_once()
        call_kwargs = ack.call_args[1]
        assert call_kwargs["response_action"] == "errors"

    @patch(
        "firetower.incidents.serializers.on_incident_created",
        side_effect=RuntimeError("boom"),
    )
    @patch("firetower.slack_app.handlers.new_incident.get_or_create_user_from_slack_id")
    def test_save_failure_sends_error_dm(self, mock_get_user, mock_hook):
        mock_get_user.return_value = self.user

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_TEST"}}
        view = {
            "state": {
                "values": {
                    "title_block": {"title": {"value": "Test Incident"}},
                    "severity_block": {
                        "severity": {
                            "selected_option": {"value": "P1"},
                        }
                    },
                    "description_block": {"description": {"value": "Description"}},
                    "private_block": {"is_private": {"selected_options": []}},
                }
            }
        }

        handle_new_incident_submission(ack, body, view, client)

        ack.assert_called_once_with()
        client.chat_postMessage.assert_called_once()
        msg = client.chat_postMessage.call_args[1]["text"]
        assert "Something went wrong" in msg
        assert "#team-sre" in msg
