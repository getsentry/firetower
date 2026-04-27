import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from firetower.incidents.models import ExternalLink, ExternalLinkType
from firetower.slack_app.handlers.statuspage import (
    _build_statuspage_modal,
    _parse_private_metadata,
    handle_statuspage_command,
    handle_statuspage_confirm_resolve,
    handle_statuspage_reset_and_resolve,
    handle_statuspage_resolve_anyway,
    handle_statuspage_submission,
)

from .conftest import CHANNEL_ID


class TestBuildStatuspageModal:
    def test_new_post_has_title_input(self):
        with patch(
            "firetower.slack_app.handlers.statuspage.StatuspageService"
        ) as MockService:
            MockService.return_value.configured = False
            modal = _build_statuspage_modal(
                channel_id=CHANNEL_ID,
                incident_title="Test Outage",
                incident_severity="P1",
            )

        assert modal["callback_id"] == "statuspage_modal"
        assert modal["title"]["text"] == "New Statuspage Post"
        block_ids = [b.get("block_id") for b in modal["blocks"]]
        assert "title_block" in block_ids
        assert "message_block" in block_ids
        assert "status_block" in block_ids
        assert "impact_block" in block_ids

    def test_new_post_shows_title_as_placeholder(self):
        with patch(
            "firetower.slack_app.handlers.statuspage.StatuspageService"
        ) as MockService:
            MockService.return_value.configured = False
            modal = _build_statuspage_modal(
                channel_id=CHANNEL_ID,
                incident_title="Database Issues",
                incident_severity="P2",
            )

        title_block = next(
            b for b in modal["blocks"] if b.get("block_id") == "title_block"
        )
        assert "initial_value" not in title_block["element"]
        assert title_block["element"]["placeholder"]["text"] == "Database Issues"

    def test_new_post_derives_impact_from_severity(self):
        with patch(
            "firetower.slack_app.handlers.statuspage.StatuspageService"
        ) as MockService:
            MockService.return_value.configured = False
            modal = _build_statuspage_modal(
                channel_id=CHANNEL_ID,
                incident_title="Outage",
                incident_severity="P0",
            )

        impact_block = next(
            b for b in modal["blocks"] if b.get("block_id") == "impact_block"
        )
        assert impact_block["element"]["initial_option"]["value"] == "critical"

    def test_update_shows_title_as_text(self):
        sp_incident = {
            "name": "Existing Issue",
            "impact": "major",
            "incident_updates": [
                {
                    "status": "identified",
                    "created_at": "2024-01-01T00:00:00Z",
                    "affected_components": [],
                }
            ],
        }
        with patch(
            "firetower.slack_app.handlers.statuspage.StatuspageService"
        ) as MockService:
            MockService.return_value.configured = False
            modal = _build_statuspage_modal(
                channel_id=CHANNEL_ID,
                incident_title="Test",
                incident_severity="P1",
                statuspage_incident=sp_incident,
            )

        assert modal["title"]["text"] == "Update Statuspage"
        block_ids = [b.get("block_id") for b in modal["blocks"]]
        assert "title_block" not in block_ids
        assert "impact_block" not in block_ids

        section_blocks = [b for b in modal["blocks"] if b.get("type") == "section"]
        assert any("Existing Issue" in b["text"]["text"] for b in section_blocks)

    def test_update_prefills_current_status(self):
        sp_incident = {
            "name": "Issue",
            "impact": "minor",
            "incident_updates": [
                {
                    "status": "monitoring",
                    "created_at": "2024-01-02T00:00:00Z",
                    "affected_components": [],
                },
                {
                    "status": "investigating",
                    "created_at": "2024-01-01T00:00:00Z",
                    "affected_components": [],
                },
            ],
        }
        with patch(
            "firetower.slack_app.handlers.statuspage.StatuspageService"
        ) as MockService:
            MockService.return_value.configured = False
            modal = _build_statuspage_modal(
                channel_id=CHANNEL_ID,
                incident_title="Test",
                incident_severity="P1",
                statuspage_incident=sp_incident,
            )

        status_block = next(
            b for b in modal["blocks"] if b.get("block_id") == "status_block"
        )
        assert status_block["element"]["initial_option"]["value"] == "monitoring"

    def test_component_fetch_failure_shows_warning(self):
        with patch(
            "firetower.slack_app.handlers.statuspage.StatuspageService"
        ) as MockService:
            instance = MockService.return_value
            instance.configured = True
            instance.get_components.side_effect = requests.RequestException("boom")
            modal = _build_statuspage_modal(
                channel_id=CHANNEL_ID,
                incident_title="Test",
                incident_severity="P1",
            )

        section_blocks = [b for b in modal["blocks"] if b.get("type") == "section"]
        assert any(
            "Could not load Statuspage components" in b["text"]["text"]
            for b in section_blocks
        )

    def test_components_rendered_when_service_configured(self):
        mock_components = [
            {"id": "c1", "name": "API", "group_id": None, "position": 1},
            {"id": "c2", "name": "Dashboard", "group_id": None, "position": 2},
        ]
        with patch(
            "firetower.slack_app.handlers.statuspage.StatuspageService"
        ) as MockService:
            instance = MockService.return_value
            instance.configured = True
            instance.get_components.return_value = (mock_components, {})
            modal = _build_statuspage_modal(
                channel_id=CHANNEL_ID,
                incident_title="Test",
                incident_severity="P1",
            )

        component_blocks = [
            b
            for b in modal["blocks"]
            if b.get("block_id") in ("component_c1", "component_c2")
        ]
        assert len(component_blocks) == 2


@pytest.mark.django_db
class TestStatuspageCommand:
    def test_opens_modal_for_new_post(self, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID, "trigger_id": "T123"}
        command = {"command": "/ft"}
        respond = MagicMock()

        with (
            patch(
                "firetower.slack_app.handlers.statuspage.StatuspageService"
            ) as MockService,
            patch("firetower.slack_app.bolt.get_bolt_app") as mock_app,
        ):
            instance = MockService.return_value
            instance.configured = True
            instance.get_components.return_value = ([], {})
            handle_statuspage_command(ack, body, command, respond)

            ack.assert_called_once()
            mock_app.return_value.client.views_open.assert_called_once()
            view = mock_app.return_value.client.views_open.call_args[1]["view"]
            assert view["callback_id"] == "statuspage_modal"
            assert view["title"]["text"] == "New Statuspage Post"

    def test_unconfigured_service_responds_error(self, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID, "trigger_id": "T123"}
        command = {"command": "/ft"}
        respond = MagicMock()

        with patch(
            "firetower.slack_app.handlers.statuspage.StatuspageService"
        ) as MockService:
            MockService.return_value.configured = False
            handle_statuspage_command(ack, body, command, respond)

        ack.assert_called_once()
        assert "not configured" in respond.call_args[0][0]

    def test_opens_modal_for_existing_post(self, incident):
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.STATUSPAGE,
            url="https://test.statuspage.io/incidents/sp123",
        )

        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID, "trigger_id": "T123"}
        command = {"command": "/ft"}
        respond = MagicMock()

        sp_data = {
            "id": "sp123",
            "name": "Existing",
            "impact": "major",
            "incident_updates": [
                {
                    "status": "investigating",
                    "created_at": "2024-01-01T00:00:00Z",
                    "affected_components": [],
                }
            ],
        }

        with (
            patch(
                "firetower.slack_app.handlers.statuspage.StatuspageService"
            ) as MockService,
            patch("firetower.slack_app.bolt.get_bolt_app") as mock_app,
        ):
            instance = MockService.return_value
            instance.configured = True
            instance.extract_incident_id_from_url.return_value = "sp123"
            instance.get_incident.return_value = sp_data
            instance.get_components.return_value = ([], {})

            handle_statuspage_command(ack, body, command, respond)

            view = mock_app.return_value.client.views_open.call_args[1]["view"]
            assert view["title"]["text"] == "Update Statuspage"

    def test_no_incident_responds_error(self, db):
        ack = MagicMock()
        body = {"channel_id": "C_UNKNOWN", "trigger_id": "T123"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_statuspage_command(ack, body, command, respond)

        ack.assert_called_once()
        assert "Could not find" in respond.call_args[0][0]

    def test_no_trigger_id(self, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_statuspage_command(ack, body, command, respond)

        ack.assert_called_once()
        assert "trigger_id" in respond.call_args[0][0]


@pytest.mark.django_db
class TestStatuspageSubmission:
    def _make_view(
        self,
        *,
        status="investigating",
        message="Looking into it",
        title="Outage",
        impact="major",
        channel_id=CHANNEL_ID,
        components=None,
        component_names=None,
    ):
        values: dict = {
            "status_block": {
                "status_select": {
                    "selected_option": {"value": status},
                }
            },
            "message_block": {
                "message_input": {"value": message},
            },
            "title_block": {
                "title_input": {"value": title},
            },
            "impact_block": {
                "impact_select": {
                    "selected_option": {"value": impact},
                }
            },
        }
        if components:
            for comp_id, comp_status in components.items():
                values[f"component_{comp_id}"] = {
                    "component_impact_select": {
                        "selected_option": {"value": comp_status},
                    }
                }
        return {
            "state": {"values": values},
            "private_metadata": json.dumps(
                {
                    "channel_id": channel_id,
                    "component_names": component_names or {},
                }
            ),
        }

    def test_creates_new_statuspage_incident(self, incident):
        ack = MagicMock()
        body = {}
        view = self._make_view()
        client = MagicMock()

        with patch(
            "firetower.slack_app.handlers.statuspage.StatuspageService"
        ) as MockService:
            instance = MockService.return_value
            instance.configured = True
            instance.create_incident.return_value = {"id": "new_sp_123"}
            instance.get_incident_url.return_value = (
                "https://test.statuspage.io/incidents/new_sp_123"
            )

            handle_statuspage_submission(ack, body, view, client)

        ack.assert_called_once()
        instance.create_incident.assert_called_once_with(
            title="Outage",
            status="investigating",
            message="Looking into it",
            impact="major",
            components=None,
        )

        link = ExternalLink.objects.get(
            incident=incident, type=ExternalLinkType.STATUSPAGE
        )
        assert link.url == "https://test.statuspage.io/incidents/new_sp_123"

        assert "created" in client.chat_postMessage.call_args[1]["text"]

    def test_creates_with_components(self, incident):
        ack = MagicMock()
        body = {}
        view = self._make_view(components={"comp1": "major_outage"})
        client = MagicMock()

        with patch(
            "firetower.slack_app.handlers.statuspage.StatuspageService"
        ) as MockService:
            instance = MockService.return_value
            instance.configured = True
            instance.create_incident.return_value = {"id": "new_sp_456"}
            instance.get_incident_url.return_value = (
                "https://test.statuspage.io/incidents/new_sp_456"
            )

            handle_statuspage_submission(ack, body, view, client)

        instance.create_incident.assert_called_once_with(
            title="Outage",
            status="investigating",
            message="Looking into it",
            impact="major",
            components={"comp1": "major_outage"},
        )

    def test_updates_existing_statuspage_incident(self, incident):
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.STATUSPAGE,
            url="https://test.statuspage.io/incidents/existing_sp",
        )

        ack = MagicMock()
        body = {}
        view = self._make_view(status="identified", message="Found the cause")
        client = MagicMock()

        with patch(
            "firetower.slack_app.handlers.statuspage.StatuspageService"
        ) as MockService:
            instance = MockService.return_value
            instance.configured = True
            instance.extract_incident_id_from_url.return_value = "existing_sp"
            instance.update_incident.return_value = {"id": "existing_sp"}
            instance.get_incident_url.return_value = (
                "https://test.statuspage.io/incidents/existing_sp"
            )

            handle_statuspage_submission(ack, body, view, client)

        instance.update_incident.assert_called_once_with(
            incident_id="existing_sp",
            status="identified",
            message="Found the cause",
            components=None,
        )
        assert "updated" in client.chat_postMessage.call_args[1]["text"]

    def test_empty_message_returns_error(self, incident):
        ack = MagicMock()
        body = {}
        view = self._make_view(message="")
        client = MagicMock()

        handle_statuspage_submission(ack, body, view, client)

        ack.assert_called_once_with(
            response_action="errors",
            errors={"message_block": "Message is required."},
        )
        client.chat_postMessage.assert_not_called()

    def test_unconfigured_service_responds_error(self, incident):
        ack = MagicMock()
        body = {}
        view = self._make_view()
        client = MagicMock()

        with patch(
            "firetower.slack_app.handlers.statuspage.StatuspageService"
        ) as MockService:
            instance = MockService.return_value
            instance.configured = False

            handle_statuspage_submission(ack, body, view, client)

        ack.assert_called_once_with()
        client.chat_postMessage.assert_called_once()
        assert "not configured" in client.chat_postMessage.call_args[1]["text"]

    def test_api_error_sends_failure_message(self, incident):
        ack = MagicMock()
        body = {}
        view = self._make_view()
        client = MagicMock()

        with patch(
            "firetower.slack_app.handlers.statuspage.StatuspageService"
        ) as MockService:
            instance = MockService.return_value
            instance.configured = True
            instance.create_incident.side_effect = requests.RequestException(
                "API error"
            )

            handle_statuspage_submission(ack, body, view, client)

        ack.assert_called_once()
        assert "went wrong" in client.chat_postMessage.call_args[1]["text"]
        assert not ExternalLink.objects.filter(
            incident=incident, type=ExternalLinkType.STATUSPAGE
        ).exists()

    def test_no_incident_for_channel(self, db):
        ack = MagicMock()
        body = {}
        view = self._make_view(channel_id="C_NONEXISTENT")
        client = MagicMock()

        with patch(
            "firetower.slack_app.handlers.statuspage.StatuspageService"
        ) as MockService:
            MockService.return_value.configured = True
            handle_statuspage_submission(ack, body, view, client)

        ack.assert_called_once()
        client.chat_postMessage.assert_called_once()
        assert (
            "Could not find an incident" in client.chat_postMessage.call_args[1]["text"]
        )

    def test_rejects_empty_title(self, incident):
        ack = MagicMock()
        body = {}
        view = self._make_view(title="")
        client = MagicMock()

        handle_statuspage_submission(ack, body, view, client)

        ack.assert_called_once_with(
            response_action="errors",
            errors={"title_block": "Title is required."},
        )


class TestStatuspageResetAndResolve:
    def _make_body(self, data: dict) -> dict:
        return {
            "view": {
                "id": "V_WARNING",
                "private_metadata": json.dumps(data),
            }
        }

    def test_sets_all_components_operational_and_processes(self):
        data = {
            "channel_id": CHANNEL_ID,
            "status": "resolved",
            "title": "Outage",
            "message": "Resolved",
            "impact": "major",
            "components": {"c1": "major_outage", "c2": "degraded_performance"},
            "component_names": {"c1": "API", "c2": "Web"},
        }
        ack = MagicMock()
        body = self._make_body(data)
        client = MagicMock()

        with (
            patch(
                "firetower.slack_app.handlers.statuspage._process_statuspage_submission",
                return_value=True,
            ) as mock_process,
            patch("firetower.slack_app.bolt.get_bolt_app") as mock_app,
        ):
            handle_statuspage_reset_and_resolve(ack, body, client)

        ack.assert_called_once_with()
        mock_process.assert_called_once()
        passed_data = mock_process.call_args[0][0]
        assert passed_data["components"] == {"c1": "operational", "c2": "operational"}
        mock_app.return_value.client.views_update.assert_called_once()
        update_kwargs = mock_app.return_value.client.views_update.call_args[1]
        assert update_kwargs["view_id"] == "V_WARNING"
        assert update_kwargs["view"]["clear_on_close"] is True
        section_text = update_kwargs["view"]["blocks"][0]["text"]["text"]
        assert "operational" in section_text
        assert "resolved" in section_text

    def test_failure_shows_failure_message(self):
        data = {
            "channel_id": CHANNEL_ID,
            "status": "resolved",
            "title": "Outage",
            "message": "Resolved",
            "impact": "major",
            "components": {"c1": "major_outage"},
            "component_names": {"c1": "API"},
        }
        ack = MagicMock()
        body = self._make_body(data)
        client = MagicMock()

        with (
            patch(
                "firetower.slack_app.handlers.statuspage._process_statuspage_submission",
                return_value=False,
            ),
            patch("firetower.slack_app.bolt.get_bolt_app") as mock_app,
        ):
            handle_statuspage_reset_and_resolve(ack, body, client)

        update_kwargs = mock_app.return_value.client.views_update.call_args[1]
        assert update_kwargs["view"]["clear_on_close"] is True
        section_text = update_kwargs["view"]["blocks"][0]["text"]["text"]
        assert "went wrong" in section_text


class TestStatuspageResolveAnyway:
    def _make_body(self, data: dict) -> dict:
        return {
            "view": {
                "id": "V_WARNING",
                "private_metadata": json.dumps(data),
            }
        }

    def test_processes_submission_and_shows_success(self):
        data = {
            "channel_id": CHANNEL_ID,
            "status": "resolved",
            "title": "Outage",
            "message": "Resolved",
            "impact": "major",
            "components": {"c1": "major_outage", "c2": "degraded_performance"},
            "component_names": {"c1": "API", "c2": "Web"},
        }
        ack = MagicMock()
        body = self._make_body(data)
        client = MagicMock()

        with (
            patch(
                "firetower.slack_app.handlers.statuspage._process_statuspage_submission",
                return_value=True,
            ) as mock_process,
            patch("firetower.slack_app.bolt.get_bolt_app") as mock_app,
        ):
            handle_statuspage_resolve_anyway(ack, body, client)

        ack.assert_called_once_with()
        mock_process.assert_called_once_with(data, client)
        passed_data = mock_process.call_args[0][0]
        assert passed_data["components"] == {
            "c1": "major_outage",
            "c2": "degraded_performance",
        }
        mock_app.return_value.client.views_update.assert_called_once()
        update_kwargs = mock_app.return_value.client.views_update.call_args[1]
        assert update_kwargs["view_id"] == "V_WARNING"
        assert update_kwargs["view"]["clear_on_close"] is True
        section_text = update_kwargs["view"]["blocks"][0]["text"]["text"]
        assert ":white_check_mark:" in section_text
        assert "left as-is" in section_text

    def test_failure_shows_failure_message(self):
        data = {
            "channel_id": CHANNEL_ID,
            "status": "resolved",
            "title": "Outage",
            "message": "Resolved",
            "impact": "major",
            "components": {"c1": "major_outage"},
            "component_names": {"c1": "API"},
        }
        ack = MagicMock()
        body = self._make_body(data)
        client = MagicMock()

        with (
            patch(
                "firetower.slack_app.handlers.statuspage._process_statuspage_submission",
                return_value=False,
            ),
            patch("firetower.slack_app.bolt.get_bolt_app") as mock_app,
        ):
            handle_statuspage_resolve_anyway(ack, body, client)

        update_kwargs = mock_app.return_value.client.views_update.call_args[1]
        assert update_kwargs["view"]["clear_on_close"] is True
        section_text = update_kwargs["view"]["blocks"][0]["text"]["text"]
        assert "went wrong" in section_text


class TestStatuspageConfirmResolve:
    def test_clears_modal_stack_and_processes_submission(self):
        data = {
            "channel_id": CHANNEL_ID,
            "status": "resolved",
            "title": "Outage",
            "message": "Resolved anyway",
            "impact": "major",
            "components": {"c1": "major_outage"},
            "component_names": {"c1": "API"},
        }
        ack = MagicMock()
        body = {}
        view = {"private_metadata": json.dumps(data)}
        client = MagicMock()

        with patch(
            "firetower.slack_app.handlers.statuspage._process_statuspage_submission",
            return_value=True,
        ) as mock_process:
            handle_statuspage_confirm_resolve(ack, body, view, client)

        ack.assert_called_once_with(response_action="clear")
        mock_process.assert_called_once_with(data, client)


class TestParsePrivateMetadata:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            (
                json.dumps({"channel_id": "C123", "component_names": {"a": "A"}}),
                {"channel_id": "C123", "component_names": {"a": "A"}},
            ),
            (
                "C_12345",
                {"channel_id": "C_12345", "component_names": {}},
            ),
            (
                json.dumps("hello"),
                {"channel_id": "", "component_names": {}},
            ),
            (
                json.dumps(None),
                {"channel_id": "", "component_names": {}},
            ),
            (
                json.dumps(123),
                {"channel_id": "", "component_names": {}},
            ),
            ("", {}),
            (None, {}),
        ],
    )
    def test_parse_private_metadata(self, raw, expected):
        assert _parse_private_metadata(raw) == expected
