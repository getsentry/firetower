from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    Tag,
    TagType,
)
from firetower.slack_app.handlers.update_incident import (
    _build_update_incident_modal,
    handle_update_command,
    handle_update_incident_submission,
)

CHANNEL_ID = "C_TEST_CHANNEL"


@pytest.fixture
def user(db):
    u = User.objects.create_user(
        username="test@example.com",
        email="test@example.com",
        first_name="Test",
        last_name="User",
    )
    ExternalProfile.objects.create(
        user=u,
        type=ExternalProfileType.SLACK,
        external_id="U_CAPTAIN",
    )
    return u


@pytest.fixture
def incident(user):
    inc = Incident(
        title="Test Incident",
        severity=IncidentSeverity.P2,
        status=IncidentStatus.ACTIVE,
        description="Original description",
        impact_summary="Original impact",
        captain=user,
        reporter=user,
    )
    inc.save()
    ExternalLink.objects.create(
        incident=inc,
        type=ExternalLinkType.SLACK,
        url=f"https://slack.com/archives/{CHANNEL_ID}",
    )
    return inc


@pytest.mark.django_db
class TestUpdateCommand:
    @patch("firetower.slack_app.bolt.get_bolt_app")
    def test_opens_modal(self, mock_get_bolt_app, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID, "trigger_id": "T12345"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_update_command(ack, body, command, respond)

        ack.assert_called_once()
        mock_get_bolt_app.return_value.client.views_open.assert_called_once()
        view = mock_get_bolt_app.return_value.client.views_open.call_args[1]["view"]
        assert view["callback_id"] == "update_incident_modal"
        assert view["private_metadata"] == CHANNEL_ID
        assert incident.incident_number in view["title"]["text"]

    def test_no_incident_responds_error(self, db):
        ack = MagicMock()
        body = {"channel_id": "C_UNKNOWN", "trigger_id": "T12345"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_update_command(ack, body, command, respond)

        ack.assert_called_once()
        respond.assert_called_once()
        assert "Could not find" in respond.call_args[0][0]

    def test_missing_trigger_id(self, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_update_command(ack, body, command, respond)

        ack.assert_called_once()
        respond.assert_called_once()
        assert "trigger_id" in respond.call_args[0][0]


@pytest.mark.django_db
class TestUpdateIncidentModal:
    def test_prefills_title(self, incident):
        modal = _build_update_incident_modal(incident, CHANNEL_ID)
        title_block = next(b for b in modal["blocks"] if b["block_id"] == "title_block")
        assert title_block["element"]["initial_value"] == "Test Incident"

    def test_prefills_severity(self, incident):
        modal = _build_update_incident_modal(incident, CHANNEL_ID)
        sev_block = next(
            b for b in modal["blocks"] if b["block_id"] == "severity_block"
        )
        assert sev_block["element"]["initial_option"]["value"] == "P2"

    def test_prefills_description(self, incident):
        modal = _build_update_incident_modal(incident, CHANNEL_ID)
        desc_block = next(
            b for b in modal["blocks"] if b["block_id"] == "description_block"
        )
        assert desc_block["element"]["initial_value"] == "Original description"

    def test_prefills_impact_summary(self, incident):
        modal = _build_update_incident_modal(incident, CHANNEL_ID)
        block = next(
            b for b in modal["blocks"] if b["block_id"] == "impact_summary_block"
        )
        assert block["element"]["initial_value"] == "Original impact"

    def test_prefills_private_checkbox(self, incident):
        incident.is_private = True
        incident.save()
        modal = _build_update_incident_modal(incident, CHANNEL_ID)
        block = next(b for b in modal["blocks"] if b["block_id"] == "private_block")
        assert "initial_options" in block["element"]
        assert block["element"]["initial_options"][0]["value"] == "private"

    def test_private_unchecked_by_default(self, incident):
        modal = _build_update_incident_modal(incident, CHANNEL_ID)
        block = next(b for b in modal["blocks"] if b["block_id"] == "private_block")
        assert "initial_options" not in block["element"]

    def test_prefills_tags(self, incident):
        tag = Tag.objects.create(name="api-server", type=TagType.AFFECTED_SERVICE)
        incident.affected_service_tags.add(tag)

        modal = _build_update_incident_modal(incident, CHANNEL_ID)
        block = next(
            b for b in modal["blocks"] if b["block_id"] == "affected_service_block"
        )
        assert "initial_options" in block["element"]
        assert block["element"]["initial_options"][0]["value"] == "api-server"

    def test_empty_tags_no_initial_options(self, incident):
        modal = _build_update_incident_modal(incident, CHANNEL_ID)
        block = next(
            b for b in modal["blocks"] if b["block_id"] == "affected_service_block"
        )
        assert "initial_options" not in block["element"]


@pytest.mark.django_db
class TestUpdateIncidentSubmission:
    @patch("firetower.incidents.serializers.on_title_changed")
    def test_updates_incident(self, mock_title_hook, incident):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = {
            "private_metadata": CHANNEL_ID,
            "state": {
                "values": {
                    "title_block": {"title": {"value": "Updated Title"}},
                    "severity_block": {
                        "severity": {"selected_option": {"value": "P1"}}
                    },
                    "description_block": {
                        "description": {"value": "Updated description"}
                    },
                    "impact_summary_block": {
                        "impact_summary": {"value": "Updated impact"}
                    },
                    "impact_type_block": {"impact_type_tags": {"selected_options": []}},
                    "affected_service_block": {
                        "affected_service_tags": {"selected_options": []}
                    },
                    "affected_region_block": {
                        "affected_region_tags": {"selected_options": []}
                    },
                    "private_block": {"is_private": {"selected_options": []}},
                }
            },
        }

        handle_update_incident_submission(ack, body, view, client)

        ack.assert_called_once_with()
        incident.refresh_from_db()
        assert incident.title == "Updated Title"
        assert incident.severity == IncidentSeverity.P1
        assert incident.description == "Updated description"
        assert incident.impact_summary == "Updated impact"
        client.chat_postMessage.assert_called_once()
        assert "updated" in client.chat_postMessage.call_args[1]["text"]

    def test_empty_title_returns_modal_error(self, incident):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = {
            "private_metadata": CHANNEL_ID,
            "state": {
                "values": {
                    "title_block": {"title": {"value": ""}},
                    "severity_block": {
                        "severity": {"selected_option": {"value": "P1"}}
                    },
                    "description_block": {"description": {"value": ""}},
                    "impact_summary_block": {"impact_summary": {"value": ""}},
                    "impact_type_block": {"impact_type_tags": {"selected_options": []}},
                    "affected_service_block": {
                        "affected_service_tags": {"selected_options": []}
                    },
                    "affected_region_block": {
                        "affected_region_tags": {"selected_options": []}
                    },
                    "private_block": {"is_private": {"selected_options": []}},
                }
            },
        }

        handle_update_incident_submission(ack, body, view, client)

        ack.assert_called_once()
        call_kwargs = ack.call_args[1]
        assert call_kwargs["response_action"] == "errors"
        client.chat_postMessage.assert_not_called()

    def test_missing_incident_does_not_crash(self, db):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = {
            "private_metadata": "C_NONEXISTENT",
            "state": {
                "values": {
                    "title_block": {"title": {"value": "Some Title"}},
                    "severity_block": {
                        "severity": {"selected_option": {"value": "P2"}}
                    },
                    "description_block": {"description": {"value": ""}},
                    "impact_summary_block": {"impact_summary": {"value": ""}},
                    "impact_type_block": {"impact_type_tags": {"selected_options": []}},
                    "affected_service_block": {
                        "affected_service_tags": {"selected_options": []}
                    },
                    "affected_region_block": {
                        "affected_region_tags": {"selected_options": []}
                    },
                    "private_block": {"is_private": {"selected_options": []}},
                }
            },
        }

        handle_update_incident_submission(ack, body, view, client)

        ack.assert_called_once()
        client.chat_postMessage.assert_not_called()
