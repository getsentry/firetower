from unittest.mock import MagicMock, patch

import pytest

from firetower.incidents.models import IncidentStatus
from firetower.slack_app.handlers.page import (
    handle_page_command,
    handle_page_submission,
)

from .conftest import CHANNEL_ID

MOCK_PD_CONFIG = {
    "API_TOKEN": "test-token",
    "ESCALATION_POLICIES": {
        "IMOC": {"id": "PIMOC01", "integration_key": "imoc-integration-key"},
        "PROD_ENG": {"id": "PPE001", "integration_key": "prod-eng-integration-key"},
    },
}


@pytest.mark.django_db
class TestPageCommand:
    @patch("firetower.slack_app.bolt.get_bolt_app")
    def test_opens_modal_with_configured_policies(
        self, mock_get_bolt_app, incident, settings
    ):
        settings.PAGERDUTY = MOCK_PD_CONFIG
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID, "trigger_id": "T12345"}
        command = {"command": "/inc"}
        respond = MagicMock()

        handle_page_command(ack, body, command, respond)

        ack.assert_called_once()
        mock_get_bolt_app.return_value.client.views_open.assert_called_once()
        view = mock_get_bolt_app.return_value.client.views_open.call_args[1]["view"]
        assert view["callback_id"] == "page_incident_modal"
        assert view["private_metadata"] == CHANNEL_ID
        policies_block = next(
            b for b in view["blocks"] if b.get("block_id") == "policies_block"
        )
        options = policies_block["element"]["options"]
        assert [o["value"] for o in options] == ["IMOC", "PROD_ENG"]
        assert [o["text"]["text"] for o in options] == [
            "IMOC",
            "Production Engineering",
        ]
        assert "optional" not in policies_block
        note_block = next(
            b for b in view["blocks"] if b.get("block_id") == "note_block"
        )
        assert note_block["optional"] is True

    @patch("firetower.slack_app.bolt.get_bolt_app")
    def test_missing_trigger_id_responds_error(
        self, mock_get_bolt_app, incident, settings
    ):
        settings.PAGERDUTY = MOCK_PD_CONFIG
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/inc"}
        respond = MagicMock()

        handle_page_command(ack, body, command, respond)

        ack.assert_called_once()
        assert "trigger_id" in respond.call_args[0][0]
        mock_get_bolt_app.return_value.client.views_open.assert_not_called()

    @patch("firetower.slack_app.bolt.get_bolt_app")
    def test_terminal_status_incident_responds_error(
        self, mock_get_bolt_app, incident, settings
    ):
        settings.PAGERDUTY = MOCK_PD_CONFIG
        incident.status = IncidentStatus.DONE
        incident.save(update_fields=["status"])
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID, "trigger_id": "T12345"}
        command = {"command": "/inc"}
        respond = MagicMock()

        handle_page_command(ack, body, command, respond)

        ack.assert_called_once()
        assert "Cannot page" in respond.call_args[0][0]
        mock_get_bolt_app.return_value.client.views_open.assert_not_called()

    @patch("firetower.slack_app.bolt.get_bolt_app")
    def test_no_incident_responds_error(self, mock_get_bolt_app, db, settings):
        settings.PAGERDUTY = MOCK_PD_CONFIG
        ack = MagicMock()
        body = {"channel_id": "C_UNKNOWN", "trigger_id": "T12345"}
        command = {"command": "/inc"}
        respond = MagicMock()

        handle_page_command(ack, body, command, respond)

        ack.assert_called_once()
        assert "Could not find" in respond.call_args[0][0]
        mock_get_bolt_app.return_value.client.views_open.assert_not_called()

    @patch("firetower.slack_app.bolt.get_bolt_app")
    def test_pagerduty_unconfigured_responds_error(
        self, mock_get_bolt_app, incident, settings
    ):
        settings.PAGERDUTY = None
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID, "trigger_id": "T12345"}
        command = {"command": "/inc"}
        respond = MagicMock()

        handle_page_command(ack, body, command, respond)

        ack.assert_called_once()
        assert "not configured" in respond.call_args[0][0]
        mock_get_bolt_app.return_value.client.views_open.assert_not_called()


@pytest.mark.django_db
class TestPageSubmission:
    @patch("firetower.slack_app.handlers.page.manual_page")
    def test_pages_selected_policies(self, mock_manual_page, incident, settings):
        settings.FIRETOWER_BASE_URL = "https://firetower.example.com"
        mock_manual_page.return_value = {"IMOC", "PROD_ENG"}
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_PAGER"}}
        view = {
            "private_metadata": CHANNEL_ID,
            "state": {
                "values": {
                    "policies_block": {
                        "policies": {
                            "selected_options": [
                                {"value": "IMOC"},
                                {"value": "PROD_ENG"},
                            ]
                        }
                    },
                    "note_block": {"note": {"value": ""}},
                }
            },
        }

        handle_page_submission(ack, body, view, client)

        ack.assert_called_once_with()
        mock_manual_page.assert_called_once()
        args, kwargs = mock_manual_page.call_args
        assert args[0] == incident
        assert args[1] == ["IMOC", "PROD_ENG"]
        assert kwargs["channel_id"] == CHANNEL_ID
        assert kwargs["note"] is None
        msg = client.chat_postMessage.call_args[1]["text"]
        assert "<@U_PAGER>" in msg
        assert "*IMOC*" in msg
        assert "*Production Engineering*" in msg
        assert incident.incident_number in msg

    @patch("firetower.slack_app.handlers.page.manual_page")
    def test_note_trimmed_passed_and_posted(self, mock_manual_page, incident, settings):
        settings.FIRETOWER_BASE_URL = "https://firetower.example.com"
        mock_manual_page.return_value = {"IMOC"}
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_PAGER"}}
        view = {
            "private_metadata": CHANNEL_ID,
            "state": {
                "values": {
                    "policies_block": {
                        "policies": {"selected_options": [{"value": "IMOC"}]}
                    },
                    "note_block": {"note": {"value": "  db is on fire  "}},
                }
            },
        }

        handle_page_submission(ack, body, view, client)

        assert mock_manual_page.call_args.kwargs["note"] == "db is on fire"
        msg = client.chat_postMessage.call_args[1]["text"]
        assert "db is on fire" in msg

    @patch("firetower.slack_app.handlers.page.manual_page")
    def test_no_selection_returns_errors(self, mock_manual_page, incident):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_PAGER"}}
        view = {
            "private_metadata": CHANNEL_ID,
            "state": {
                "values": {
                    "policies_block": {"policies": {"selected_options": []}},
                }
            },
        }

        handle_page_submission(ack, body, view, client)

        ack.assert_called_once_with(
            response_action="errors",
            errors={"policies_block": "Select at least one escalation policy to page."},
        )
        mock_manual_page.assert_not_called()
        client.chat_postMessage.assert_not_called()

    @patch("firetower.slack_app.handlers.page.manual_page")
    def test_none_paged_posts_failure(self, mock_manual_page, incident, settings):
        settings.FIRETOWER_BASE_URL = "https://firetower.example.com"
        mock_manual_page.return_value = set()
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_PAGER"}}
        view = {
            "private_metadata": CHANNEL_ID,
            "state": {
                "values": {
                    "policies_block": {
                        "policies": {"selected_options": [{"value": "IMOC"}]}
                    },
                    "note_block": {"note": {"value": ""}},
                }
            },
        }

        handle_page_submission(ack, body, view, client)

        msg = client.chat_postMessage.call_args[1]["text"]
        assert "escalate manually" in msg

    @patch("firetower.slack_app.handlers.page.manual_page")
    def test_partial_failure_reports_both(self, mock_manual_page, incident, settings):
        settings.FIRETOWER_BASE_URL = "https://firetower.example.com"
        mock_manual_page.return_value = {"IMOC"}
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_PAGER"}}
        view = {
            "private_metadata": CHANNEL_ID,
            "state": {
                "values": {
                    "policies_block": {
                        "policies": {
                            "selected_options": [
                                {"value": "IMOC"},
                                {"value": "PROD_ENG"},
                            ]
                        }
                    },
                    "note_block": {"note": {"value": ""}},
                }
            },
        }

        handle_page_submission(ack, body, view, client)

        msg = client.chat_postMessage.call_args[1]["text"]
        assert "paged *IMOC*" in msg
        assert "Failed to page *Production Engineering*" in msg

    @patch("firetower.slack_app.handlers.page.manual_page")
    def test_terminal_status_incident_is_noop(
        self, mock_manual_page, incident, settings
    ):
        settings.FIRETOWER_BASE_URL = "https://firetower.example.com"
        incident.status = IncidentStatus.DONE
        incident.save(update_fields=["status"])
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_PAGER"}}
        view = {
            "private_metadata": CHANNEL_ID,
            "state": {
                "values": {
                    "policies_block": {
                        "policies": {"selected_options": [{"value": "IMOC"}]}
                    },
                    "note_block": {"note": {"value": ""}},
                }
            },
        }

        handle_page_submission(ack, body, view, client)

        ack.assert_called_once_with()
        mock_manual_page.assert_not_called()
        client.chat_postMessage.assert_called_once()
        msg = client.chat_postMessage.call_args[1]["text"]
        assert "Not paging" in msg
        assert incident.status in msg

    @patch("firetower.slack_app.handlers.page.manual_page")
    def test_missing_incident_does_not_crash(self, mock_manual_page, db):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_PAGER"}}
        view = {
            "private_metadata": "C_NONEXISTENT",
            "state": {
                "values": {
                    "policies_block": {
                        "policies": {"selected_options": [{"value": "IMOC"}]}
                    },
                }
            },
        }

        handle_page_submission(ack, body, view, client)

        ack.assert_called_once()
        mock_manual_page.assert_not_called()
        client.chat_postMessage.assert_not_called()
