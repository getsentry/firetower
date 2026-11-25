from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from time import monotonic
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.db import InterfaceError, OperationalError, connection
from django.utils import timezone

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.incidents.models import Incident, IncidentSeverity, IncidentStatus
from firetower.slack_app.bolt import _register_views
from firetower.slack_app.handlers.new_incident import (
    _build_new_incident_modal,
    _build_recent_incident_blocks,
    _lookup_recent_incidents,
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

    @pytest.mark.parametrize("configured_minutes", [None, 1, 5, 30])
    def test_time_window_privacy_and_order(self, settings, configured_minutes):
        if configured_minutes is not None:
            settings.SLACK = {
                **settings.SLACK,
                "RECENT_INCIDENT_WINDOW_MINUTES": configured_minutes,
            }
        window_minutes = 10 if configured_minutes is None else configured_minutes
        now = timezone.now()
        boundary = Incident.objects.create(title="Boundary", severity="P2")
        newest = Incident.objects.create(title="Newest", severity="P1")
        old = Incident.objects.create(title="Old", severity="P3")
        Incident.objects.create(title="Secret", severity="P0", is_private=True)
        Incident.objects.filter(id=boundary.id).update(
            created_at=now - timedelta(minutes=window_minutes)
        )
        Incident.objects.filter(id=newest.id).update(created_at=now)
        Incident.objects.filter(id=old.id).update(
            created_at=now - timedelta(minutes=window_minutes, seconds=1)
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
        unit = "minute" if window_minutes == 1 else "minutes"
        assert blocks[0]["text"]["text"] == (
            ":warning: *Is this incident already being handled?*\n"
            f"These incidents were opened in the last {window_minutes} {unit}. "
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

        with django_assert_num_queries(1):
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


@pytest.mark.django_db(transaction=True)
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
        client.views_update.assert_not_called()
        assert Incident.objects.count() == 1
        ack.assert_called_once()
        assert ack.call_args.kwargs["response_action"] == "update"
        confirmation = ack.call_args.kwargs["view"]
        assert confirmation["callback_id"] == "new_incident_confirmation_modal"
        assert confirmation["submit"]["text"] == "Create anyway"
        assert confirmation["private_metadata"] == "C_INVOKE"
        assert confirmation["blocks"][0]["block_id"] == "recent_incidents_warning"
        original_inputs = [b for b in submitted_view["blocks"] if b["type"] == "input"]
        inputs = [b for b in confirmation["blocks"] if b["type"] == "input"]
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
        confirmation = ack.call_args.kwargs["view"]
        confirmation["state"] = submitted_view["state"]
        ack.reset_mock()

        with patch(
            "firetower.slack_app.handlers.new_incident._check_recent_incidents"
        ) as lookup:
            handle_new_incident_submission(ack, body, confirmation, client)

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
    def test_no_recent_incidents_creates_immediately(self, create, submitted_view):
        ack = MagicMock()
        client = MagicMock()

        handle_new_incident_submission(
            ack, {"user": {"id": "U_REPORTER"}}, submitted_view, client
        )

        ack.assert_called_once_with()
        client.views_update.assert_not_called()
        create.assert_called_once()

    @pytest.mark.parametrize("error", [OperationalError, InterfaceError, ValueError])
    @patch(
        "firetower.slack_app.handlers.new_incident._create_incident_via_db",
        return_value=None,
    )
    def test_lookup_failure_does_not_block_creation(
        self, create, error, submitted_view, caplog
    ):
        ack = MagicMock()
        client = MagicMock()
        with (
            caplog.at_level("INFO"),
            patch(
                "firetower.slack_app.handlers.new_incident._lookup_recent_incidents",
                side_effect=error("Lookup unavailable"),
            ),
        ):
            handle_new_incident_submission(
                ack, {"user": {"id": "U_REPORTER"}}, submitted_view, client
            )

        ack.assert_called_once_with()
        client.views_update.assert_not_called()
        create.assert_called_once()
        assert "Recent-incident check failed" in caplog.text

    @patch("firetower.slack_app.handlers.new_incident._recent_incident_executor")
    @patch(
        "firetower.slack_app.handlers.new_incident._create_incident_via_db",
        return_value=None,
    )
    def test_timeout_creates_immediately(
        self, create, executor, submitted_view, caplog
    ):
        ack = MagicMock()
        client = MagicMock()
        future = executor.submit.return_value
        future.result.side_effect = TimeoutError

        with caplog.at_level("INFO"):
            handle_new_incident_submission(
                ack, {"user": {"id": "U_REPORTER"}}, submitted_view, client
            )

        future.result.assert_called_once_with(timeout=0.5)
        future.cancel.assert_called_once_with()
        ack.assert_called_once_with()
        client.views_update.assert_not_called()
        create.assert_called_once()
        assert "exceeded 500 ms" in caplog.text

    @patch("firetower.slack_app.handlers.new_incident._recent_incident_executor")
    @patch(
        "firetower.slack_app.handlers.new_incident._create_incident_via_db",
        return_value=None,
    )
    def test_worker_submission_failure_creates_immediately(
        self, create, executor, submitted_view
    ):
        executor.submit.side_effect = RuntimeError("Executor unavailable")
        ack = MagicMock()

        handle_new_incident_submission(
            ack, {"user": {"id": "U_REPORTER"}}, submitted_view, MagicMock()
        )

        ack.assert_called_once_with()
        create.assert_called_once()

    @patch(
        "firetower.slack_app.handlers.new_incident._create_incident_via_db",
        return_value=None,
    )
    def test_does_not_wait_for_worker_or_apply_late_results(
        self, create, submitted_view
    ):
        release = Event()
        ack = MagicMock()
        client = MagicMock()

        def slow_lookup():
            release.wait()
            return [{"block_id": "recent_incidents_warning"}]

        with ThreadPoolExecutor(max_workers=1) as executor:
            try:
                with (
                    patch(
                        "firetower.slack_app.handlers.new_incident._recent_incident_executor",
                        executor,
                    ),
                    patch(
                        "firetower.slack_app.handlers.new_incident._lookup_recent_incidents",
                        side_effect=slow_lookup,
                    ),
                    patch(
                        "firetower.slack_app.handlers.new_incident._RECENT_INCIDENT_TIMEOUT_SECONDS",
                        0.02,
                    ),
                ):
                    started = monotonic()
                    handle_new_incident_submission(
                        ack, {"user": {"id": "U_REPORTER"}}, submitted_view, client
                    )
                    assert monotonic() - started < 1
                    ack.assert_called_once_with()
                    create.assert_called_once()
            finally:
                release.set()

        ack.assert_called_once_with()
        create.assert_called_once()
        client.views_update.assert_not_called()

    @patch("firetower.slack_app.handlers.new_incident._create_fallback_channel")
    @patch(
        "firetower.slack_app.handlers.new_incident._create_incident_via_db",
        side_effect=OperationalError,
    )
    @patch(
        "firetower.slack_app.handlers.new_incident._lookup_recent_incidents",
        side_effect=OperationalError,
    )
    def test_db_outage_still_creates_fallback(
        self, lookup, create, fallback, submitted_view
    ):
        ack = MagicMock()
        client = MagicMock()

        handle_new_incident_submission(
            ack, {"user": {"id": "U_REPORTER"}}, submitted_view, client
        )

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
        handle_new_incident_submission(ack, body, submitted_view, MagicMock())
        confirmation = ack.call_args.kwargs["view"]
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

    def test_initial_form_uses_create(self, submitted_view):
        assert submitted_view["submit"]["text"] == "Create"

    @patch("firetower.slack_app.handlers.new_incident._check_recent_incidents")
    @patch(
        "firetower.slack_app.handlers.new_incident._create_incident_via_db",
        return_value=None,
    )
    def test_acknowledges_after_lookup_before_creation(
        self, create, lookup, submitted_view
    ):
        ack = MagicMock()

        def check():
            ack.assert_not_called()
            create.assert_not_called()
            return []

        def save(*args, **kwargs):
            ack.assert_called_once_with()

        lookup.side_effect = check
        create.side_effect = save

        handle_new_incident_submission(
            ack, {"user": {"id": "U_REPORTER"}}, submitted_view, MagicMock()
        )

        lookup.assert_called_once_with()
        create.assert_called_once()

    @patch("firetower.slack_app.handlers.new_incident._check_recent_incidents")
    def test_invalid_title_does_not_check_recent_incidents(
        self, lookup, submitted_view
    ):
        submitted_view["state"]["values"]["title_block"]["title"]["value"] = ""
        ack = MagicMock()

        handle_new_incident_submission(
            ack, {"user": {"id": "U_REPORTER"}}, submitted_view, MagicMock()
        )

        ack.assert_called_once_with(
            response_action="errors",
            errors={"title_block": "This field is required."},
        )
        lookup.assert_not_called()


@pytest.mark.django_db(transaction=True)
class TestRecentIncidentQueryTimeout:
    def test_slow_query_is_canceled_and_connection_recovers(self):
        def slow_query():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_sleep(5)")

        started = monotonic()
        with (
            patch(
                "firetower.slack_app.handlers.new_incident._build_recent_incident_blocks",
                side_effect=slow_query,
            ),
            pytest.raises(OperationalError, match="statement timeout"),
        ):
            _lookup_recent_incidents()

        assert monotonic() - started < 2
        with connection.cursor() as cursor:
            cursor.execute("SHOW statement_timeout")
            assert cursor.fetchone()[0] == "0"

    def test_success_closes_worker_connection(self, recent_incident):
        assert _lookup_recent_incidents()
        assert connection.connection is None


def test_confirmation_handler_is_registered():
    app = MagicMock()

    _register_views(app)

    assert ("new_incident_confirmation_modal",) in [
        call.args for call in app.view.call_args_list
    ]
