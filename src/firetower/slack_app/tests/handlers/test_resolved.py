from unittest.mock import MagicMock, patch

import pytest

from firetower.incidents.models import IncidentSeverity, IncidentStatus, Tag, TagType
from firetower.slack_app.handlers.resolved import (
    _build_resolved_modal,
    handle_resolved_command,
    handle_resolved_submission,
)

from .conftest import CHANNEL_ID


def _make_resolved_view(severity="P1", captain="U_CAPTAIN", title="Test Incident"):
    return {
        "private_metadata": CHANNEL_ID,
        "state": {
            "values": {
                "severity_block": {
                    "severity_select": {"selected_option": {"value": severity}}
                },
                "captain_block": {"captain_select": {"selected_user": captain}},
                "title_block": {"title": {"value": title}},
                "description_block": {"description": {"value": "Updated desc"}},
                "impact_summary_block": {"impact_summary": {"value": "Updated impact"}},
                "impact_type_block": {"impact_type_tags": {"selected_options": []}},
                "affected_service_block": {
                    "affected_service_tags": {"selected_options": []}
                },
                "affected_region_block": {
                    "affected_region_tags": {"selected_options": []}
                },
            }
        },
    }


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
class TestResolvedModal:
    def test_contains_metadata_fields(self, incident):
        modal = _build_resolved_modal(incident, CHANNEL_ID)
        block_ids = [b["block_id"] for b in modal["blocks"] if "block_id" in b]
        assert "severity_block" in block_ids
        assert "captain_block" in block_ids
        assert "title_block" in block_ids
        assert "description_block" in block_ids
        assert "impact_summary_block" in block_ids
        assert "impact_type_block" in block_ids
        assert "affected_service_block" in block_ids
        assert "affected_region_block" in block_ids

    def test_contains_context_message(self, incident):
        modal = _build_resolved_modal(incident, CHANNEL_ID)
        section = modal["blocks"][0]
        assert "contained" in section["text"]["text"]

    def test_prefills_title(self, incident):
        modal = _build_resolved_modal(incident, CHANNEL_ID)
        block = next(b for b in modal["blocks"] if b.get("block_id") == "title_block")
        assert block["element"]["initial_value"] == "Test Incident"

    def test_prefills_severity(self, incident):
        modal = _build_resolved_modal(incident, CHANNEL_ID)
        block = next(
            b for b in modal["blocks"] if b.get("block_id") == "severity_block"
        )
        assert block["element"]["initial_option"]["value"] == "P2"

    def test_prefills_description(self, incident):
        incident.description = "Some description"
        incident.save()
        modal = _build_resolved_modal(incident, CHANNEL_ID)
        block = next(
            b for b in modal["blocks"] if b.get("block_id") == "description_block"
        )
        assert block["element"]["initial_value"] == "Some description"

    def test_prefills_impact_summary(self, incident):
        incident.impact_summary = "Some impact"
        incident.save()
        modal = _build_resolved_modal(incident, CHANNEL_ID)
        block = next(
            b for b in modal["blocks"] if b.get("block_id") == "impact_summary_block"
        )
        assert block["element"]["initial_value"] == "Some impact"

    def test_prefills_tags(self, incident):
        tag = Tag.objects.create(name="api-server", type=TagType.AFFECTED_SERVICE)
        incident.affected_service_tags.add(tag)
        modal = _build_resolved_modal(incident, CHANNEL_ID)
        block = next(
            b for b in modal["blocks"] if b.get("block_id") == "affected_service_block"
        )
        assert "initial_options" in block["element"]
        assert block["element"]["initial_options"][0]["value"] == "api-server"


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
        view = _make_resolved_view(severity="P1")

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
        view = _make_resolved_view(severity="P4")

        handle_resolved_submission(ack, body, view, client)

        ack.assert_called_once_with()
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.DONE

    @patch("firetower.incidents.serializers.on_status_changed")
    @patch("firetower.incidents.serializers.on_title_changed")
    @patch("firetower.slack_app.handlers.resolved.get_or_create_user_from_slack_id")
    def test_saves_metadata_fields(
        self, mock_get_user, mock_title_hook, mock_status_hook, user, incident
    ):
        mock_get_user.return_value = user
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = _make_resolved_view(severity="P3", title="Updated Title")

        handle_resolved_submission(ack, body, view, client)

        ack.assert_called_once_with()
        incident.refresh_from_db()
        assert incident.title == "Updated Title"
        assert incident.description == "Updated desc"
        assert incident.impact_summary == "Updated impact"

    def test_missing_captain_returns_error(self, incident):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = _make_resolved_view(captain=None)

        handle_resolved_submission(ack, body, view, client)

        ack.assert_called_once()
        call_kwargs = ack.call_args[1]
        assert call_kwargs["response_action"] == "errors"
        assert "captain" in str(call_kwargs["errors"]).lower()
