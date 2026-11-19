from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.db import InterfaceError, OperationalError
from django.utils import timezone
from slack_sdk.errors import SlackApiError

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.incidents.models import Incident, IncidentSeverity, IncidentStatus
from firetower.slack_app.bolt import _register_views
from firetower.slack_app.handlers.new_incident import (
    _build_new_incident_modal,
    _build_recent_incident_blocks,
    handle_new_incident_submission,
    handle_severity_action,
)


@pytest.fixture
def submitted_view():
    view = _build_new_incident_modal(
        channel_id="C_INVOKE", user_id="U_REPORTER", severity="P1"
    )
    view["id"] = "V_TEST"
    view["state"] = {
        "values": {
            "title_block": {"title": {"value": "New incident"}},
            "severity_block": {"severity": {"selected_option": {"value": "P1"}}},
            "description_block": {"description": {"value": "Description"}},
            "impact_summary_block": {"impact_summary": {"value": "Impact"}},
            "alert_url_block": {"alert_url": {"value": "https://sentry.io/issues/123"}},
            "captain_block": {"captain_select": {"selected_user": "U_CAPTAIN"}},
            "options_block": {
                "incident_options": {
                    "selected_options": [
                        {"value": "private"},
                        {"value": "skip_paging"},
                    ]
                }
            },
        }
    }
    return view


@pytest.fixture
def recent_incident(db):
    return Incident.objects.create(
        title="Existing incident", severity=IncidentSeverity.P1
    )


@pytest.mark.django_db
class TestRecentIncidentBlocks:
    def test_no_recent_incidents(self):
        assert _build_recent_incident_blocks() == []

    def test_time_window_privacy_and_order(self):
        now = timezone.now()
        boundary = Incident.objects.create(title="Boundary", severity="P2")
        newest = Incident.objects.create(title="Newest", severity="P1")
        old = Incident.objects.create(title="Old", severity="P3")
        Incident.objects.create(title="Secret", severity="P0", is_private=True)
        Incident.objects.filter(id=boundary.id).update(
            created_at=now - timedelta(minutes=10)
        )
        Incident.objects.filter(id=newest.id).update(created_at=now)
        Incident.objects.filter(id=old.id).update(
            created_at=now - timedelta(minutes=10, seconds=1)
        )

        with patch(
            "firetower.slack_app.handlers.new_incident.timezone.now", return_value=now
        ):
            blocks = _build_recent_incident_blocks()

        assert [block["block_id"] for block in blocks] == [
            "recent_incidents_warning",
            f"recent_incident_{newest.id}",
            f"recent_incident_{boundary.id}",
        ]
        assert blocks[0]["text"]["text"] == (
            ":warning: *Is this incident already being handled?*\n"
            "These incidents were opened in the last 10 minutes. "
            "If one matches, cancel and join the existing incident. "
            "Otherwise, choose *Create anyway*."
        )
        assert blocks[1]["text"]["text"] == (
            f"[P1] <{settings.FIRETOWER_BASE_URL}/{newest.incident_number}"
            f"|{newest.incident_number} Newest>"
        )

    @pytest.mark.parametrize(
        ("status", "should_warn"),
        [
            (IncidentStatus.ACTIVE, True),
            (IncidentStatus.MITIGATED, True),
            (IncidentStatus.POSTMORTEM, False),
            (IncidentStatus.DONE, False),
            (IncidentStatus.CANCELED, False),
        ],
    )
    def test_only_warns_for_unresolved_incidents(self, status, should_warn):
        incident = Incident.objects.create(
            title="Recent incident", severity="P1", status=status
        )

        blocks = _build_recent_incident_blocks()

        if should_warn:
            assert [block["block_id"] for block in blocks] == [
                "recent_incidents_warning",
                f"recent_incident_{incident.id}",
            ]
        else:
            assert blocks == []

    def test_closed_incidents_do_not_hide_open_incidents(self):
        incident = Incident.objects.create(title="Open incident", severity="P1")
        for i in range(10):
            Incident.objects.create(
                title=f"Canceled {i}", severity="P1", status=IncidentStatus.CANCELED
            )

        blocks = _build_recent_incident_blocks()

        assert [block["block_id"] for block in blocks] == [
            "recent_incidents_warning",
            f"recent_incident_{incident.id}",
        ]

    @pytest.mark.parametrize("has_slack_profile", [True, False])
    def test_topic_format_includes_captain(self, has_slack_profile):
        captain = User.objects.create_user(
            username="captain@example.com", first_name="Jane", last_name="Doe"
        )
        if has_slack_profile:
            ExternalProfile.objects.create(
                user=captain, type=ExternalProfileType.SLACK, external_id="U_CAPTAIN"
            )
        incident = Incident.objects.create(
            title="Existing incident", severity="P1", captain=captain
        )

        blocks = _build_recent_incident_blocks()

        captain_label = "<@U_CAPTAIN>" if has_slack_profile else "Jane Doe"
        assert blocks[1]["text"]["text"] == (
            f"[P1] <{settings.FIRETOWER_BASE_URL}/{incident.incident_number}"
            f"|{incident.incident_number} Existing incident> | IC: {captain_label}"
        )

    def test_batches_captain_lookups(self, django_assert_num_queries):
        for i in range(3):
            captain = User.objects.create_user(username=f"captain-{i}")
            ExternalProfile.objects.create(
                user=captain,
                type=ExternalProfileType.SLACK,
                external_id=f"U_CAPTAIN_{i}",
            )
            Incident.objects.create(
                title=f"Incident {i}", severity="P1", captain=captain
            )

        with django_assert_num_queries(2):
            blocks = _build_recent_incident_blocks()

        assert len(blocks) == 4
        assert [block["text"]["text"].split(" | IC: ")[1] for block in blocks[1:]] == [
            "<@U_CAPTAIN_2>",
            "<@U_CAPTAIN_1>",
            "<@U_CAPTAIN_0>",
        ]

    def test_private_incident_alone_does_not_prompt(self):
        Incident.objects.create(title="Secret", severity="P0", is_private=True)

        assert _build_recent_incident_blocks() == []

    def test_caps_results_at_ten_newest(self):
        incidents = [
            Incident.objects.create(title=f"Incident {i}", severity="P1")
            for i in range(11)
        ]

        blocks = _build_recent_incident_blocks()

        assert len(blocks) == 11
        assert [block["block_id"] for block in blocks[1:]] == [
            f"recent_incident_{incident.id}" for incident in reversed(incidents[1:])
        ]

    def test_escapes_titles(self):
        Incident.objects.create(
            title="<!channel> & <https://example.com|click>", severity="P1"
        )

        blocks = _build_recent_incident_blocks()

        assert (
            "&lt;!channel&gt; &amp; &lt;https://example.com|click&gt;"
            in blocks[1]["text"]["text"]
        )
        assert "<!channel>" not in str(blocks)


@pytest.mark.django_db
class TestRecentIncidentConfirmation:
    @patch("firetower.slack_app.handlers.new_incident._create_incident_via_db")
    def test_prompts_before_creating(self, create, recent_incident, submitted_view):
        ack = MagicMock()
        client = MagicMock()

        handle_new_incident_submission(
            ack, {"user": {"id": "U_REPORTER"}}, submitted_view, client
        )

        create.assert_not_called()
        client.chat_postMessage.assert_not_called()
        assert Incident.objects.count() == 1
        ack.assert_called_once()
        assert ack.call_args.kwargs["response_action"] == "update"
        checking = ack.call_args.kwargs["view"]
        assert checking["callback_id"] == "new_incident_confirmation_modal"
        assert checking["submit"]["text"] == "Create anyway"
        assert (
            "Checking for recently opened incidents"
            in checking["blocks"][0]["text"]["text"]
        )
        client.views_update.assert_called_once()
        assert client.views_update.call_args.kwargs["view_id"] == "V_TEST"
        confirmation = client.views_update.call_args.kwargs["view"]
        assert confirmation["callback_id"] == "new_incident_confirmation_modal"
        assert confirmation["submit"]["text"] == "Create anyway"
        assert confirmation["private_metadata"] == "C_INVOKE"
        assert confirmation["blocks"][0]["block_id"] == "recent_incidents_warning"
        original_inputs = [b for b in submitted_view["blocks"] if b["type"] == "input"]
        for modal in (checking, confirmation):
            inputs = [b for b in modal["blocks"] if b["type"] == "input"]
            assert [b["block_id"] for b in inputs] == [
                b["block_id"] for b in original_inputs
            ]
            assert [b["element"]["action_id"] for b in inputs] == [
                b["element"]["action_id"] for b in original_inputs
            ]
        options = next(
            b for b in confirmation["blocks"] if b.get("block_id") == "options_block"
        )
        assert {o["value"] for o in options["element"]["initial_options"]} == {
            "private",
            "skip_paging",
        }

    @patch(
        "firetower.slack_app.handlers.new_incident._create_incident_via_db",
        return_value=None,
    )
    def test_confirmation_submits_preserved_form(
        self, create, recent_incident, submitted_view
    ):
        ack = MagicMock()
        body = {"user": {"id": "U_REPORTER"}}
        client = MagicMock()
        handle_new_incident_submission(ack, body, submitted_view, client)
        confirmation = client.views_update.call_args.kwargs["view"]
        confirmation["state"] = submitted_view["state"]
        ack.reset_mock()

        with patch(
            "firetower.slack_app.handlers.new_incident._build_recent_incident_blocks"
        ) as lookup:
            handle_new_incident_submission(ack, body, confirmation, MagicMock())

        lookup.assert_not_called()
        ack.assert_called_once_with()
        create.assert_called_once()
        form, reporter, is_private, _client = create.call_args.args
        assert reporter == "U_REPORTER"
        assert is_private is True
        assert create.call_args.kwargs["skip_paging"] is True
        assert form["title"] == "New incident"
        assert form["severity"] == "P1"
        assert form["description"] == "Description"
        assert form["impact_summary"] == "Impact"
        assert form["alert_url"] == "https://sentry.io/issues/123"
        assert form["captain_slack_id"] == "U_CAPTAIN"

    @patch(
        "firetower.slack_app.handlers.new_incident._create_incident_via_db",
        return_value=None,
    )
    def test_no_recent_incidents_shows_create_confirmation(
        self, create, submitted_view
    ):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_REPORTER"}}

        handle_new_incident_submission(ack, body, submitted_view, client)

        ack.assert_called_once()
        assert ack.call_args.kwargs["response_action"] == "update"
        create.assert_not_called()
        confirmation = client.views_update.call_args.kwargs["view"]
        assert confirmation["callback_id"] == "new_incident_confirmation_modal"
        assert confirmation["submit"]["text"] == "Create"
        assert [b["block_id"] for b in confirmation["blocks"]] == [
            b["block_id"] for b in submitted_view["blocks"]
        ]
        confirmation["state"] = submitted_view["state"]
        ack.reset_mock()

        handle_new_incident_submission(ack, body, confirmation, client)

        ack.assert_called_once_with()
        create.assert_called_once()

    @pytest.mark.parametrize("error", [OperationalError, InterfaceError])
    @patch(
        "firetower.slack_app.handlers.new_incident._create_incident_via_db",
        return_value=None,
    )
    def test_lookup_failure_does_not_block_creation(
        self, create, error, submitted_view
    ):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_REPORTER"}}

        def failed_lookup():
            ack.assert_called_once()
            raise error("Database unavailable")

        with patch(
            "firetower.slack_app.handlers.new_incident._build_recent_incident_blocks",
            side_effect=failed_lookup,
        ):
            handle_new_incident_submission(ack, body, submitted_view, client)

        create.assert_not_called()
        confirmation = client.views_update.call_args.kwargs["view"]
        assert confirmation["submit"]["text"] == "Create anyway"
        assert "Could not check" in confirmation["blocks"][0]["text"]["text"]
        confirmation["state"] = submitted_view["state"]
        ack.reset_mock()

        handle_new_incident_submission(ack, body, confirmation, client)

        ack.assert_called_once_with()
        create.assert_called_once()

    @patch("firetower.slack_app.handlers.new_incident._create_fallback_channel")
    @patch(
        "firetower.slack_app.handlers.new_incident._create_incident_via_db",
        side_effect=OperationalError,
    )
    @patch(
        "firetower.slack_app.handlers.new_incident._build_recent_incident_blocks",
        side_effect=OperationalError,
    )
    def test_db_outage_still_creates_fallback(
        self, lookup, create, fallback, submitted_view
    ):
        ack = MagicMock()
        client = MagicMock()

        body = {"user": {"id": "U_REPORTER"}}
        handle_new_incident_submission(ack, body, submitted_view, client)
        fallback.assert_not_called()
        confirmation = client.views_update.call_args.kwargs["view"]
        confirmation["state"] = submitted_view["state"]
        ack.reset_mock()

        handle_new_incident_submission(ack, body, confirmation, client)

        ack.assert_called_once_with()
        fallback.assert_called_once()
        assert fallback.call_args.args[0] is client
        assert fallback.call_args.args[1] == "U_REPORTER"
        form = fallback.call_args.args[2]
        assert form["title"] == "New incident"
        assert form["is_private"] is True
        assert form["skip_paging"] is True

    def test_severity_change_preserves_confirmation(
        self, recent_incident, submitted_view
    ):
        ack = MagicMock()
        body = {"user": {"id": "U_REPORTER"}}
        check_client = MagicMock()
        handle_new_incident_submission(ack, body, submitted_view, check_client)
        confirmation = check_client.views_update.call_args.kwargs["view"]
        confirmation["id"] = "V_TEST"
        confirmation["state"] = submitted_view["state"]
        confirmation["state"]["values"]["severity_block"]["severity"][
            "selected_option"
        ] = {"value": "P3"}
        client = MagicMock()
        ack.reset_mock()

        handle_severity_action(ack, {**body, "view": confirmation}, client)

        ack.assert_called_once_with()
        client.views_update.assert_called_once()
        updated = client.views_update.call_args.kwargs["view"]
        assert updated["callback_id"] == "new_incident_confirmation_modal"
        assert updated["submit"]["text"] == "Create anyway"
        assert updated["blocks"][:2] == confirmation["blocks"][:2]
        options = next(
            b for b in updated["blocks"] if b.get("block_id") == "options_block"
        )
        assert {o["value"] for o in options["element"]["options"]} == {"private"}
        assert {o["value"] for o in options["element"]["initial_options"]} == {
            "private"
        }

    def test_details_step_uses_continue(self, submitted_view):
        assert submitted_view["submit"]["text"] == "Continue"

    @patch("firetower.slack_app.handlers.new_incident._create_incident_via_db")
    def test_closed_modal_does_not_create_incident(self, create, submitted_view):
        client = MagicMock()
        client.views_update.side_effect = SlackApiError(
            "Modal closed", response={"ok": False, "error": "not_found"}
        )

        handle_new_incident_submission(
            MagicMock(), {"user": {"id": "U_REPORTER"}}, submitted_view, client
        )

        create.assert_not_called()
        client.chat_postMessage.assert_not_called()

    @patch("firetower.slack_app.handlers.new_incident._build_recent_incident_blocks")
    @patch("firetower.slack_app.handlers.new_incident._create_incident_via_db")
    def test_acknowledges_before_lookup(self, create, lookup, submitted_view):
        ack = MagicMock()
        client = MagicMock()

        def delayed_lookup():
            ack.assert_called_once()
            assert ack.call_args.kwargs["response_action"] == "update"
            client.views_update.assert_not_called()
            create.assert_not_called()
            return []

        lookup.side_effect = delayed_lookup

        handle_new_incident_submission(
            ack, {"user": {"id": "U_REPORTER"}}, submitted_view, client
        )

        lookup.assert_called_once_with()
        client.views_update.assert_called_once()
        create.assert_not_called()

    @patch("firetower.slack_app.handlers.new_incident._build_recent_incident_blocks")
    @patch(
        "firetower.slack_app.handlers.new_incident._create_incident_via_db",
        return_value=None,
    )
    def test_can_create_while_lookup_is_pending(self, create, lookup, submitted_view):
        ack = MagicMock()
        confirm_ack = MagicMock()
        client = MagicMock()
        client.views_update.side_effect = SlackApiError(
            "Modal closed", response={"ok": False, "error": "not_found"}
        )
        body = {"user": {"id": "U_REPORTER"}}

        def delayed_lookup():
            ack.assert_called_once()
            confirmation = ack.call_args.kwargs["view"]
            assert confirmation["submit"]["text"] == "Create anyway"
            confirmation["state"] = submitted_view["state"]
            handle_new_incident_submission(confirm_ack, body, confirmation, client)
            confirm_ack.assert_called_once_with()
            create.assert_called_once()
            return []

        lookup.side_effect = delayed_lookup

        handle_new_incident_submission(ack, body, submitted_view, client)

        lookup.assert_called_once_with()
        create.assert_called_once()
        client.views_update.assert_called_once()

    def test_severity_change_keeps_empty_confirmation(self, submitted_view):
        view = {
            **_build_new_incident_modal(confirmation=True),
            "id": "V_TEST",
            "state": submitted_view["state"],
        }
        client = MagicMock()

        handle_severity_action(MagicMock(), {"view": view}, client)

        updated = client.views_update.call_args.kwargs["view"]
        assert updated["callback_id"] == "new_incident_confirmation_modal"
        assert updated["submit"]["text"] == "Create"


def test_confirmation_handler_is_registered():
    app = MagicMock()

    _register_views(app)

    assert ("new_incident_confirmation_modal",) in [
        call.args for call in app.view.call_args_list
    ]
