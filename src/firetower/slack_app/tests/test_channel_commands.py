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
)
from firetower.slack_app.bolt import handle_command
from firetower.slack_app.handlers.captain import handle_captain_command
from firetower.slack_app.handlers.dumpslack import handle_dumpslack_command
from firetower.slack_app.handlers.mitigated import (
    handle_mitigated_command,
    handle_mitigated_submission,
)
from firetower.slack_app.handlers.reopen import handle_reopen_command
from firetower.slack_app.handlers.resolved import (
    handle_resolved_command,
    handle_resolved_submission,
)
from firetower.slack_app.handlers.severity import handle_severity_command
from firetower.slack_app.handlers.statuspage import handle_statuspage_command
from firetower.slack_app.handlers.subject import handle_subject_command
from firetower.slack_app.handlers.utils import get_incident_from_channel


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
        captain=user,
        reporter=user,
    )
    inc.save()
    ExternalLink.objects.create(
        incident=inc,
        type=ExternalLinkType.SLACK,
        url="https://slack.com/archives/C_TEST_CHANNEL",
    )
    return inc


CHANNEL_ID = "C_TEST_CHANNEL"


class TestGetIncidentFromChannel:
    def test_returns_incident(self, incident):
        result = get_incident_from_channel(CHANNEL_ID)
        assert result == incident

    def test_returns_none_for_unknown_channel(self, db):
        result = get_incident_from_channel("C_UNKNOWN")
        assert result is None

    def test_returns_none_when_no_incidents(self, db):
        result = get_incident_from_channel(CHANNEL_ID)
        assert result is None


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
class TestMitigatedSubmission:
    @patch("firetower.incidents.serializers.on_status_changed")
    @patch("firetower.incidents.serializers.on_title_changed")
    def test_transitions_to_mitigated(
        self, mock_title_hook, mock_status_hook, incident
    ):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = {
            "private_metadata": CHANNEL_ID,
            "state": {
                "values": {
                    "impact_block": {"impact_update": {"value": "Reduced impact"}},
                    "todo_block": {"todo_update": {"value": "Monitor overnight"}},
                }
            },
        }

        handle_mitigated_submission(ack, body, view, client)

        ack.assert_called_once()
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.MITIGATED
        assert "Reduced impact" in incident.description
        assert "Monitor overnight" in incident.description
        client.chat_postMessage.assert_called_once()
        msg = client.chat_postMessage.call_args[1]["text"]
        assert "Mitigated" in msg

    def test_missing_incident_does_not_crash(self, db):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_CAPTAIN"}}
        view = {
            "private_metadata": "C_NONEXISTENT",
            "state": {
                "values": {
                    "impact_block": {"impact_update": {"value": "x"}},
                    "todo_block": {"todo_update": {"value": "y"}},
                }
            },
        }

        handle_mitigated_submission(ack, body, view, client)

        ack.assert_called_once()
        client.chat_postMessage.assert_not_called()


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


@pytest.mark.django_db
class TestReopenCommand:
    @patch("firetower.incidents.serializers.on_status_changed")
    @patch("firetower.incidents.serializers.on_title_changed")
    def test_reopens_mitigated_incident(
        self, mock_title_hook, mock_status_hook, incident
    ):
        incident.status = IncidentStatus.MITIGATED
        incident.save()

        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_reopen_command(ack, body, command, respond)

        ack.assert_called_once()
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.ACTIVE
        assert "reopened" in respond.call_args[0][0]

    def test_already_active_responds(self, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_reopen_command(ack, body, command, respond)

        ack.assert_called_once()
        assert "already Active" in respond.call_args[0][0]

    def test_no_incident_responds_error(self, db):
        ack = MagicMock()
        body = {"channel_id": "C_UNKNOWN"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_reopen_command(ack, body, command, respond)

        ack.assert_called_once()
        assert "Could not find" in respond.call_args[0][0]


@pytest.mark.django_db
class TestSeverityCommand:
    @patch("firetower.incidents.serializers.on_severity_changed")
    @patch("firetower.incidents.serializers.on_title_changed")
    def test_changes_severity(self, mock_title_hook, mock_sev_hook, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_severity_command(ack, body, command, respond, new_severity="P0")

        ack.assert_called_once()
        incident.refresh_from_db()
        assert incident.severity == IncidentSeverity.P0
        assert "P0" in respond.call_args[0][0]

    def test_invalid_severity(self, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_severity_command(ack, body, command, respond, new_severity="P9")

        ack.assert_called_once()
        assert "Invalid severity" in respond.call_args[0][0]

    def test_case_insensitive(self, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        with patch("firetower.incidents.serializers.on_severity_changed"):
            handle_severity_command(ack, body, command, respond, new_severity="p1")

        incident.refresh_from_db()
        assert incident.severity == IncidentSeverity.P1

    def test_no_incident_responds_error(self, db):
        ack = MagicMock()
        body = {"channel_id": "C_UNKNOWN"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_severity_command(ack, body, command, respond, new_severity="P0")

        ack.assert_called_once()
        assert "Could not find" in respond.call_args[0][0]


@pytest.mark.django_db
class TestSubjectCommand:
    @patch("firetower.incidents.serializers.on_title_changed")
    def test_updates_title(self, mock_title_hook, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_subject_command(ack, body, command, respond, new_subject="New Title")

        ack.assert_called_once()
        incident.refresh_from_db()
        assert incident.title == "New Title"
        assert "New Title" in respond.call_args[0][0]

    def test_no_incident_responds_error(self, db):
        ack = MagicMock()
        body = {"channel_id": "C_UNKNOWN"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_subject_command(ack, body, command, respond, new_subject="New Title")

        ack.assert_called_once()
        assert "Could not find" in respond.call_args[0][0]


@pytest.mark.django_db
class TestRouting:
    @patch("firetower.slack_app.bolt.statsd")
    def test_mitigated_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "mitigated", "channel_id": CHANNEL_ID, "trigger_id": "T123"}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_mitigated_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_mit_alias_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "mit", "channel_id": CHANNEL_ID, "trigger_id": "T123"}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_mitigated_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_resolved_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "resolved", "channel_id": CHANNEL_ID, "trigger_id": "T123"}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_resolved_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_fixed_alias_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "fixed", "channel_id": CHANNEL_ID, "trigger_id": "T123"}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_resolved_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_reopen_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "reopen", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_reopen_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_severity_routes_with_arg(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "severity P0", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_severity_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()
            assert mock_handler.call_args[1]["new_severity"] == "P0"

    @patch("firetower.slack_app.bolt.statsd")
    def test_severity_no_arg_shows_usage(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "severity", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        handle_command(ack=ack, body=body, command=command, respond=respond)

        ack.assert_called_once()
        assert "Usage" in respond.call_args[0][0]

    @patch("firetower.slack_app.bolt.statsd")
    def test_sev_alias_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "sev P1", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_severity_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_subject_routes_with_arg(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "subject New Title Here", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_subject_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()
            assert mock_handler.call_args[1]["new_subject"] == "New Title Here"

    @patch("firetower.slack_app.bolt.statsd")
    def test_subject_no_arg_shows_usage(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "subject", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        handle_command(ack=ack, body=body, command=command, respond=respond)

        ack.assert_called_once()
        assert "Usage" in respond.call_args[0][0]

    @patch("firetower.slack_app.bolt.statsd")
    def test_metrics_for_known_subcommands(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "reopen", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_reopen_command"):
            handle_command(ack=ack, body=body, command=command, respond=respond)

        mock_statsd.increment.assert_any_call(
            "slack_app.commands.submitted", tags=["subcommand:reopen"]
        )

    @patch("firetower.slack_app.bolt.statsd")
    def test_statuspage_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "statuspage", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch(
            "firetower.slack_app.bolt.handle_statuspage_command"
        ) as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_dumpslack_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "dumpslack", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_dumpslack_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()


class TestStatuspageCommand:
    def test_returns_not_implemented(self):
        ack = MagicMock()
        respond = MagicMock()
        command = {"command": "/ft"}

        handle_statuspage_command(ack, command, respond)

        ack.assert_called_once()
        respond.assert_called_once()
        assert "not yet implemented" in respond.call_args[0][0]
        assert "/inc statuspage" in respond.call_args[0][0]


class TestDumpslackCommand:
    def test_returns_not_implemented(self):
        ack = MagicMock()
        respond = MagicMock()
        command = {"command": "/ft"}

        handle_dumpslack_command(ack, command, respond)

        ack.assert_called_once()
        respond.assert_called_once()
        assert "not yet implemented" in respond.call_args[0][0]
        assert "/inc dumpslack" in respond.call_args[0][0]


@pytest.mark.django_db
class TestCaptainCommand:
    @patch("firetower.incidents.serializers.on_captain_changed")
    @patch("firetower.incidents.serializers.on_title_changed")
    @patch("firetower.slack_app.handlers.captain.get_or_create_user_from_slack_id")
    def test_sets_captain(
        self, mock_get_user, mock_title_hook, mock_captain_hook, user, incident
    ):
        mock_get_user.return_value = user
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_captain_command(ack, body, command, respond, user_mention="<@U_CAPTAIN>")

        ack.assert_called_once()
        incident.refresh_from_db()
        assert incident.captain == user
        assert "captain updated" in respond.call_args[0][0]

    def test_no_user_mention(self, incident):
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_captain_command(ack, body, command, respond, user_mention="notamention")

        ack.assert_called_once()
        assert "Usage" in respond.call_args[0][0]

    def test_no_incident_responds_error(self, db):
        ack = MagicMock()
        body = {"channel_id": "C_UNKNOWN"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_captain_command(ack, body, command, respond, user_mention="<@U_CAPTAIN>")

        ack.assert_called_once()
        assert "Could not find" in respond.call_args[0][0]

    @patch("firetower.slack_app.handlers.captain.get_or_create_user_from_slack_id")
    def test_user_not_found(self, mock_get_user, incident):
        mock_get_user.return_value = None
        ack = MagicMock()
        body = {"channel_id": CHANNEL_ID}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_captain_command(ack, body, command, respond, user_mention="<@U_UNKNOWN>")

        ack.assert_called_once()
        assert "Could not resolve" in respond.call_args[0][0]


@pytest.mark.django_db
class TestCaptainRouting:
    @patch("firetower.slack_app.bolt.statsd")
    def test_captain_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "captain <@U_CAPTAIN>", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_captain_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()
            assert mock_handler.call_args[1]["user_mention"] == "<@U_CAPTAIN>"

    @patch("firetower.slack_app.bolt.statsd")
    def test_ic_alias_routes(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "ic <@U_CAPTAIN>", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        with patch("firetower.slack_app.bolt.handle_captain_command") as mock_handler:
            handle_command(ack=ack, body=body, command=command, respond=respond)
            mock_handler.assert_called_once()

    @patch("firetower.slack_app.bolt.statsd")
    def test_captain_no_arg_shows_usage(self, mock_statsd, incident):
        ack = MagicMock()
        respond = MagicMock()
        body = {"text": "captain", "channel_id": CHANNEL_ID}
        command = {"command": "/ft"}

        handle_command(ack=ack, body=body, command=command, respond=respond)

        ack.assert_called_once()
        assert "Usage" in respond.call_args[0][0]
