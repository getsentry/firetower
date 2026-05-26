from unittest.mock import MagicMock, patch

import pytest

from firetower.incidents.models import IncidentStatus, Tag, TagType
from firetower.slack_app.handlers.mitigated import (
    _build_mitigated_modal,
    handle_mitigated_command,
    handle_mitigated_submission,
)

from .conftest import CHANNEL_ID


def _make_mitigated_view(
    severity="P2",
    captain="U_CAPTAIN",
    title="Test Incident",
    description="Things broke",
    impact_summary="Users affected",
    impact_type_tags=("Degraded Service",),
    service_tier="T1",
    affected_service_tags=(),
    affected_region_tags=(),
):
    def _options(values):
        return [{"value": v} for v in values]

    state_values: dict = {
        "captain_block": {"captain_select": {"selected_user": captain}},
        "title_block": {"title": {"value": title}},
        "description_block": {"description": {"value": description}},
        "impact_summary_block": {"impact_summary": {"value": impact_summary}},
        "impact_type_block": {
            "impact_type_tags": {"selected_options": _options(impact_type_tags)}
        },
        "affected_service_block": {
            "affected_service_tags": {
                "selected_options": _options(affected_service_tags)
            }
        },
        "affected_region_block": {
            "affected_region_tags": {"selected_options": _options(affected_region_tags)}
        },
    }
    if severity is not None:
        state_values["severity_block"] = {
            "severity_select": {"selected_option": {"value": severity}}
        }
    else:
        state_values["severity_block"] = {"severity_select": {}}
    if service_tier is not None:
        state_values["service_tier_block"] = {
            "service_tier_select": {"selected_option": {"value": service_tier}}
        }
    else:
        state_values["service_tier_block"] = {"service_tier_select": {}}
    return {"private_metadata": CHANNEL_ID, "state": {"values": state_values}}


@pytest.fixture
def impact_type_tag(db):
    return Tag.objects.create(name="Degraded Service", type=TagType.IMPACT_TYPE)


@pytest.mark.django_db
class TestMitigatedCommand:
    @patch("firetower.slack_app.bolt.get_bolt_app")
    def test_opens_modal(self, mock_get_bolt_app, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID, "trigger_id": "T12345"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_mitigated_command(ack, body, command, respond)

        ack.assert_called_once()
        mock_get_bolt_app.return_value.client.views_open.assert_called_once()
        view = mock_get_bolt_app.return_value.client.views_open.call_args[1]["view"]
        assert view["callback_id"] == "mitigated_incident_modal"
        assert view["private_metadata"] == CHANNEL_ID
        assert incident.incident_number in view["title"]["text"]

    def test_no_incident_responds_error(self, db):
        ack = MagicMock()
        body = {"channel_id": "C_UNKNOWN", "trigger_id": "T12345"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_mitigated_command(ack, body, command, respond)

        ack.assert_called_once()
        respond.assert_called_once()
        assert "Could not find" in respond.call_args[0][0]


@pytest.mark.django_db
class TestMitigatedModal:
    def test_contains_all_lifecycle_fields(self, incident):
        modal = _build_mitigated_modal(incident, CHANNEL_ID)
        block_ids = [b["block_id"] for b in modal["blocks"] if "block_id" in b]
        for required in (
            "captain_block",
            "severity_block",
            "title_block",
            "description_block",
            "impact_summary_block",
            "impact_type_block",
            "service_tier_block",
            "affected_service_block",
            "affected_region_block",
        ):
            assert required in block_ids

    def test_required_vs_optional_blocks(self, incident):
        modal = _build_mitigated_modal(incident, CHANNEL_ID)
        by_id = {b["block_id"]: b for b in modal["blocks"] if "block_id" in b}
        for required in (
            "captain_block",
            "severity_block",
            "title_block",
            "description_block",
            "impact_summary_block",
            "impact_type_block",
            "service_tier_block",
        ):
            assert by_id[required].get("optional", False) is False
        assert by_id["affected_service_block"]["optional"] is True
        assert by_id["affected_region_block"]["optional"] is True

    def test_prefills_title_and_severity(self, incident):
        modal = _build_mitigated_modal(incident, CHANNEL_ID)
        by_id = {b["block_id"]: b for b in modal["blocks"] if "block_id" in b}
        assert by_id["title_block"]["element"]["initial_value"] == "Test Incident"
        assert by_id["severity_block"]["element"]["initial_option"]["value"] == "P2"


@pytest.mark.django_db
class TestMitigatedSubmission:
    @patch("firetower.incidents.serializers.on_status_changed")
    @patch("firetower.incidents.serializers.on_title_changed")
    @patch("firetower.slack_app.handlers.mitigated.get_or_create_user_from_slack_id")
    def test_transitions_to_mitigated(
        self,
        mock_get_user,
        mock_title_hook,
        mock_status_hook,
        user,
        incident,
        impact_type_tag,
    ):
        mock_get_user.return_value = user
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = _make_mitigated_view()

        handle_mitigated_submission(ack, body, view, client)

        ack.assert_called_once_with()
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.MITIGATED
        assert incident.service_tier == "T1"
        assert incident.description == "Things broke"
        assert incident.impact_summary == "Users affected"
        client.chat_postMessage.assert_called_once()
        msg = client.chat_postMessage.call_args[1]["text"]
        assert "Mitigated" in msg
        assert "Action Items" in msg

    @patch("firetower.incidents.serializers.on_status_changed")
    @patch("firetower.incidents.serializers.on_title_changed")
    @patch("firetower.slack_app.handlers.mitigated.get_or_create_user_from_slack_id")
    def test_optional_affected_fields(
        self,
        mock_get_user,
        mock_title_hook,
        mock_status_hook,
        user,
        incident,
        impact_type_tag,
    ):
        mock_get_user.return_value = user
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        # Omit affected_service and affected_region — submission should still succeed.
        view = _make_mitigated_view(affected_service_tags=(), affected_region_tags=())

        handle_mitigated_submission(ack, body, view, client)

        ack.assert_called_once_with()
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.MITIGATED

    def test_missing_captain_returns_error(self, incident):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = _make_mitigated_view(captain=None)

        handle_mitigated_submission(ack, body, view, client)

        ack.assert_called_once()
        call_kwargs = ack.call_args[1]
        assert call_kwargs["response_action"] == "errors"
        assert "captain_block" in call_kwargs["errors"]

    def test_missing_impact_type_returns_error(self, incident):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = _make_mitigated_view(impact_type_tags=())

        handle_mitigated_submission(ack, body, view, client)

        ack.assert_called_once()
        call_kwargs = ack.call_args[1]
        assert call_kwargs["response_action"] == "errors"
        assert "impact_type_block" in call_kwargs["errors"]

    def test_missing_service_tier_returns_error(self, incident):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = _make_mitigated_view(service_tier=None)

        handle_mitigated_submission(ack, body, view, client)

        ack.assert_called_once()
        call_kwargs = ack.call_args[1]
        assert call_kwargs["response_action"] == "errors"
        assert "service_tier_block" in call_kwargs["errors"]

    def test_missing_description_returns_error(self, incident):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = _make_mitigated_view(description="")

        handle_mitigated_submission(ack, body, view, client)

        ack.assert_called_once()
        call_kwargs = ack.call_args[1]
        assert call_kwargs["response_action"] == "errors"
        assert "description_block" in call_kwargs["errors"]

    def test_missing_impact_summary_returns_error(self, incident):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = _make_mitigated_view(impact_summary="")

        handle_mitigated_submission(ack, body, view, client)

        ack.assert_called_once()
        call_kwargs = ack.call_args[1]
        assert call_kwargs["response_action"] == "errors"
        assert "impact_summary_block" in call_kwargs["errors"]
