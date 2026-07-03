from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.contrib.auth.models import User

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentCounter,
    IncidentSeverity,
)
from firetower.slack_app.bolt import handle_command
from firetower.slack_app.handlers.backfill_incident import (
    _parse_channel_id_from_args,
    handle_backfill_command,
    handle_backfill_submission,
)


class TestParseChannelIdFromArgs:
    def test_slack_channel_mention(self):
        assert _parse_channel_id_from_args("<#C12345ABC|general>") == "C12345ABC"

    def test_raw_channel_id(self):
        assert _parse_channel_id_from_args("C12345ABC") == "C12345ABC"

    def test_no_channel(self):
        assert _parse_channel_id_from_args("some random text") is None

    def test_empty_string(self):
        assert _parse_channel_id_from_args("") is None


@pytest.mark.django_db
class TestBackfillSubcommandRouting:
    def _make_body(self, text="", command="/ft"):
        return {"text": text, "command": command}

    def _make_command(self, command="/ft", text=""):
        return {"command": command, "text": text}

    @patch("firetower.slack_app.handlers.backfill_incident._slack_service")
    @patch("firetower.slack_app.bolt.get_bolt_app")
    @patch("firetower.slack_app.bolt.statsd")
    @patch("firetower.slack_app.bolt.close_old_connections")
    def test_backfill_routes_correctly(
        self, _mock_close, mock_statsd, mock_get_bolt_app, mock_slack_svc
    ):
        mock_slack_svc.get_channel_info.return_value = {
            "id": "C_TEST",
            "name": f"{settings.PROJECT_KEY.lower()}-2050",
            "is_private": False,
        }
        ack = MagicMock()
        respond = MagicMock()
        body = self._make_body(text="backfill")
        body["trigger_id"] = "T12345"
        body["channel_id"] = "C_TEST"
        body["user_id"] = "U_TEST"
        command = self._make_command()

        handle_command(ack=ack, body=body, command=command, respond=respond)

        ack.assert_called_once()
        mock_get_bolt_app.return_value.client.views_open.assert_called_once()


@pytest.mark.django_db
class TestBackfillCommand:
    @patch("firetower.slack_app.bolt.get_bolt_app")
    @patch("firetower.slack_app.handlers.backfill_incident._slack_service")
    def test_opens_modal(self, mock_slack_svc, mock_get_bolt_app):
        mock_slack_svc.get_channel_info.return_value = {
            "id": "C_TEST",
            "name": f"{settings.PROJECT_KEY.lower()}-2050",
            "is_private": False,
        }
        ack = MagicMock()
        body = {"trigger_id": "T12345", "channel_id": "C_TEST", "user_id": "U_TEST"}
        command = {"command": "/ft", "text": "backfill"}
        respond = MagicMock()

        handle_backfill_command(ack, body, command, respond)

        ack.assert_called_once()
        mock_get_bolt_app.return_value.client.views_open.assert_called_once()
        view = mock_get_bolt_app.return_value.client.views_open.call_args[1]["view"]
        assert view["callback_id"] == "backfill_incident_modal"

    @patch("firetower.slack_app.handlers.backfill_incident._slack_service")
    def test_rejects_non_incident_channel(self, mock_slack_svc):
        mock_slack_svc.get_channel_info.return_value = {
            "id": "C_RANDOM",
            "name": "random-channel",
            "is_private": False,
        }
        ack = MagicMock()
        body = {"channel_id": "C_RANDOM"}
        command = {"command": "/ft", "text": "backfill"}
        respond = MagicMock()

        handle_backfill_command(ack, body, command, respond)

        respond.assert_called_once()
        msg = respond.call_args[0][0]
        assert "only allowed on incident channels" in msg

    @patch(
        "firetower.slack_app.handlers.backfill_incident.sync_incident_participants_from_slack"
    )
    @patch("firetower.slack_app.handlers.backfill_incident._slack_service")
    @patch("firetower.slack_app.bolt.get_bolt_app")
    def test_retries_setup_on_already_linked_channel(
        self, mock_get_bolt_app, mock_slack_svc, mock_sync
    ):
        mock_slack_svc.get_channel_info.return_value = {
            "id": "C_EXISTING",
            "name": f"{settings.PROJECT_KEY.lower()}-1234",
            "is_private": False,
        }
        mock_slack_svc.join_channel.return_value = True
        user = User.objects.create_user(
            username="test@example.com", email="test@example.com"
        )
        inc = Incident(
            title="Existing", severity=IncidentSeverity.P2, captain=user, reporter=user
        )
        inc.save()
        ExternalLink.objects.create(
            incident=inc,
            type=ExternalLinkType.SLACK,
            url="https://T0000.slack.com/archives/C_EXISTING",
        )

        ack = MagicMock()
        body = {"channel_id": "C_EXISTING", "user_id": "U_TEST"}
        command = {"command": "/ft", "text": "backfill"}
        respond = MagicMock()

        handle_backfill_command(ack, body, command, respond)

        respond.assert_called_once()
        msg = respond.call_args[0][0]
        assert "already linked" in msg
        assert "Retrying channel setup" in msg
        mock_slack_svc.join_channel.assert_called_once_with("C_EXISTING")
        mock_slack_svc.set_channel_topic.assert_called_once()
        mock_slack_svc.add_bookmark.assert_called_once()

    @patch("firetower.slack_app.handlers.backfill_incident._slack_service")
    def test_channel_from_args(self, mock_slack_svc):
        mock_slack_svc.get_channel_info.return_value = {
            "id": "CARG12345",
            "name": f"{settings.PROJECT_KEY.lower()}-2050",
            "is_private": False,
        }
        ack = MagicMock()
        body = {
            "trigger_id": "T12345",
            "text": f"backfill <#CARG12345|{settings.PROJECT_KEY.lower()}-2050>",
            "channel_id": "C_OTHER",
            "user_id": "U_TEST",
        }
        command = {
            "command": "/ft",
            "text": f"backfill <#CARG12345|{settings.PROJECT_KEY.lower()}-2050>",
        }
        respond = MagicMock()

        with patch("firetower.slack_app.bolt.get_bolt_app") as mock_app:
            handle_backfill_command(ack, body, command, respond)
            mock_app.return_value.client.views_open.assert_called_once()
            view = mock_app.return_value.client.views_open.call_args[1]["view"]
            assert view["private_metadata"] == "CARG12345"

    def test_no_channel_responds_with_usage(self):
        ack = MagicMock()
        body = {"channel_id": ""}
        command = {"command": "/ft", "text": "backfill"}
        respond = MagicMock()

        handle_backfill_command(ack, body, command, respond)

        respond.assert_called_once()
        msg = respond.call_args[0][0]
        assert "Could not determine channel" in msg


@pytest.mark.django_db
class TestBackfillSubmission:
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
        IncidentCounter.objects.update_or_create(pk=1, defaults={"next_id": 2050})

    def _build_view(self, channel_id="C_TEST", title="Test Backfill"):
        return {
            "private_metadata": channel_id,
            "state": {
                "values": {
                    "title_block": {"title": {"value": title}},
                    "severity_block": {
                        "severity": {"selected_option": {"value": "P2"}}
                    },
                    "description_block": {"description": {"value": "Backfill desc"}},
                    "impact_summary_block": {"impact_summary": {"value": ""}},
                }
            },
        }

    @patch(
        "firetower.slack_app.handlers.backfill_incident.sync_incident_participants_from_slack"
    )
    @patch("firetower.slack_app.handlers.backfill_incident._slack_service")
    @patch(
        "firetower.slack_app.handlers.backfill_incident.get_or_create_user_from_slack_id"
    )
    @patch("firetower.incidents.serializers.on_incident_created")
    def test_creates_incident_and_links_channel(
        self, mock_hook, mock_get_user, mock_slack_svc, mock_sync
    ):
        mock_get_user.return_value = self.user
        mock_slack_svc.build_channel_url.return_value = (
            "https://T0000.slack.com/archives/C_TEST"
        )
        mock_slack_svc.get_channel_info.return_value = {
            "id": "C_TEST",
            "name": f"{settings.PROJECT_KEY.lower()}-2050",
            "is_private": False,
        }
        mock_slack_svc.join_channel.return_value = True

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_TEST"}}

        handle_backfill_submission(ack, body, self._build_view(), client)

        ack.assert_called_once_with()
        incident = Incident.objects.get(title="Test Backfill")
        assert incident.severity == IncidentSeverity.P2
        assert incident.captain == self.user
        assert incident.reporter == self.user

        slack_link = ExternalLink.objects.get(
            incident=incident, type=ExternalLinkType.SLACK
        )
        assert "C_TEST" in slack_link.url

        mock_hook.assert_not_called()
        mock_slack_svc.join_channel.assert_called_once_with("C_TEST")
        mock_slack_svc.set_channel_topic.assert_called_once()
        mock_slack_svc.add_bookmark.assert_called_once()
        mock_sync.assert_called_once_with(incident, force=True)

    @patch("firetower.slack_app.handlers.backfill_incident._slack_service")
    @patch(
        "firetower.slack_app.handlers.backfill_incident.get_or_create_user_from_slack_id"
    )
    @patch("firetower.incidents.serializers.on_incident_created")
    def test_bot_cant_join_still_creates_incident(
        self, mock_hook, mock_get_user, mock_slack_svc
    ):
        mock_get_user.return_value = self.user
        mock_slack_svc.build_channel_url.return_value = (
            "https://T0000.slack.com/archives/C_TEST"
        )
        mock_slack_svc.get_channel_info.return_value = {
            "id": "C_TEST",
            "name": f"{settings.PROJECT_KEY.lower()}-2050",
            "is_private": False,
        }
        mock_slack_svc.join_channel.return_value = False

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_TEST"}}

        handle_backfill_submission(ack, body, self._build_view(), client)

        incident = Incident.objects.get(title="Test Backfill")
        assert incident is not None

        slack_link = ExternalLink.objects.get(
            incident=incident, type=ExternalLinkType.SLACK
        )
        assert slack_link is not None

        mock_slack_svc.set_channel_topic.assert_not_called()
        mock_slack_svc.add_bookmark.assert_not_called()

        client.chat_postMessage.assert_called_once()
        msg = client.chat_postMessage.call_args[1]["text"]
        assert "could not join" in msg
        assert "/ft backfill" in msg

    @patch("firetower.slack_app.handlers.backfill_incident._slack_service")
    @patch(
        "firetower.slack_app.handlers.backfill_incident.get_or_create_user_from_slack_id"
    )
    @patch("firetower.incidents.serializers.on_incident_created")
    def test_skips_setup_for_archived_channel(
        self, mock_hook, mock_get_user, mock_slack_svc
    ):
        mock_get_user.return_value = self.user
        mock_slack_svc.build_channel_url.return_value = (
            "https://T0000.slack.com/archives/C_TEST"
        )
        mock_slack_svc.get_channel_info.return_value = {
            "id": "C_TEST",
            "name": f"{settings.PROJECT_KEY.lower()}-2050",
            "is_private": False,
            "is_archived": True,
        }

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_TEST"}}

        handle_backfill_submission(ack, body, self._build_view(), client)

        incident = Incident.objects.get(title="Test Backfill")
        assert incident is not None

        mock_slack_svc.join_channel.assert_not_called()
        mock_slack_svc.set_channel_topic.assert_not_called()
        mock_slack_svc.add_bookmark.assert_not_called()
        client.chat_postMessage.assert_not_called()

    @patch(
        "firetower.slack_app.handlers.backfill_incident.sync_incident_participants_from_slack"
    )
    @patch("firetower.slack_app.handlers.backfill_incident._slack_service")
    @patch(
        "firetower.slack_app.handlers.backfill_incident.get_or_create_user_from_slack_id"
    )
    @patch("firetower.incidents.serializers.on_incident_created")
    def test_renames_channel_when_name_does_not_match(
        self, mock_hook, mock_get_user, mock_slack_svc, mock_sync
    ):
        mock_get_user.return_value = self.user
        mock_slack_svc.build_channel_url.return_value = (
            "https://T0000.slack.com/archives/C_TEST"
        )
        mock_slack_svc.get_channel_info.return_value = {
            "id": "C_TEST",
            "name": "wrong-name",
            "is_private": False,
        }
        mock_slack_svc.join_channel.return_value = True
        mock_slack_svc.rename_channel.return_value = True

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_TEST"}}

        handle_backfill_submission(ack, body, self._build_view(), client)

        incident = Incident.objects.get(title="Test Backfill")
        expected_name = incident.incident_number.lower()
        mock_slack_svc.rename_channel.assert_called_once_with("C_TEST", expected_name)
        mock_slack_svc.set_channel_topic.assert_called_once()

    @patch(
        "firetower.slack_app.handlers.backfill_incident.sync_incident_participants_from_slack"
    )
    @patch("firetower.slack_app.handlers.backfill_incident._slack_service")
    @patch(
        "firetower.slack_app.handlers.backfill_incident.get_or_create_user_from_slack_id"
    )
    @patch("firetower.incidents.serializers.on_incident_created")
    def test_rename_failure_posts_in_channel(
        self, mock_hook, mock_get_user, mock_slack_svc, mock_sync
    ):
        mock_get_user.return_value = self.user
        mock_slack_svc.build_channel_url.return_value = (
            "https://T0000.slack.com/archives/C_TEST"
        )
        mock_slack_svc.get_channel_info.return_value = {
            "id": "C_TEST",
            "name": "wrong-name",
            "is_private": False,
        }
        mock_slack_svc.join_channel.return_value = True
        mock_slack_svc.rename_channel.return_value = False

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_TEST"}}

        handle_backfill_submission(ack, body, self._build_view(), client)

        incident = Incident.objects.get(title="Test Backfill")
        expected_name = incident.incident_number.lower()
        mock_slack_svc.rename_channel.assert_called_once_with("C_TEST", expected_name)
        rename_msg_call = [
            c
            for c in client.chat_postMessage.call_args_list
            if c[1].get("channel") == "C_TEST"
            and "could not rename" in c[1].get("text", "")
        ]
        assert len(rename_msg_call) == 1
        assert expected_name in rename_msg_call[0][1]["text"]

    @patch(
        "firetower.slack_app.handlers.backfill_incident.sync_incident_participants_from_slack"
    )
    @patch("firetower.slack_app.handlers.backfill_incident._slack_service")
    @patch(
        "firetower.slack_app.handlers.backfill_incident.get_or_create_user_from_slack_id"
    )
    @patch("firetower.incidents.serializers.on_incident_created")
    def test_skips_rename_when_name_already_matches(
        self, mock_hook, mock_get_user, mock_slack_svc, mock_sync
    ):
        mock_get_user.return_value = self.user
        mock_slack_svc.build_channel_url.return_value = (
            "https://T0000.slack.com/archives/C_TEST"
        )
        mock_slack_svc.join_channel.return_value = True

        def channel_info_matching_incident(channel_id):
            try:
                incident = Incident.objects.get(title="Test Backfill")
                name = incident.incident_number.lower()
            except Incident.DoesNotExist:
                name = f"{settings.PROJECT_KEY.lower()}-unknown"
            return {
                "id": channel_id,
                "name": name,
                "is_private": False,
            }

        mock_slack_svc.get_channel_info.side_effect = channel_info_matching_incident

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_TEST"}}

        handle_backfill_submission(ack, body, self._build_view(), client)

        mock_slack_svc.rename_channel.assert_not_called()

    @patch(
        "firetower.slack_app.handlers.backfill_incident.sync_incident_participants_from_slack"
    )
    @patch("firetower.slack_app.handlers.backfill_incident._slack_service")
    @patch(
        "firetower.slack_app.handlers.backfill_incident.get_or_create_user_from_slack_id"
    )
    @patch("firetower.incidents.serializers.on_incident_created")
    def test_defaults_to_private_when_channel_info_unavailable(
        self, mock_hook, mock_get_user, mock_slack_svc, mock_sync
    ):
        mock_get_user.return_value = self.user
        mock_slack_svc.build_channel_url.return_value = (
            "https://T0000.slack.com/archives/C_TEST"
        )
        mock_slack_svc.get_channel_info.return_value = None
        mock_slack_svc.join_channel.return_value = True

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_TEST"}}

        handle_backfill_submission(ack, body, self._build_view(), client)

        incident = Incident.objects.get(title="Test Backfill")
        assert incident.is_private is True

    @patch(
        "firetower.slack_app.handlers.backfill_incident.sync_incident_participants_from_slack"
    )
    @patch("firetower.slack_app.handlers.backfill_incident._slack_service")
    @patch(
        "firetower.slack_app.handlers.backfill_incident.get_or_create_user_from_slack_id"
    )
    @patch("firetower.incidents.serializers.on_incident_created")
    def test_retries_channel_info_after_join_when_initial_fetch_failed(
        self, mock_hook, mock_get_user, mock_slack_svc, mock_sync
    ):
        mock_get_user.return_value = self.user
        mock_slack_svc.build_channel_url.return_value = (
            "https://T0000.slack.com/archives/C_TEST"
        )
        mock_slack_svc.get_channel_info.side_effect = [
            None,
            None,
            {
                "id": "C_TEST",
                "name": "wrong-name",
                "is_private": False,
            },
        ]
        mock_slack_svc.join_channel.return_value = True
        mock_slack_svc.rename_channel.return_value = True

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_TEST"}}

        handle_backfill_submission(ack, body, self._build_view(), client)

        incident = Incident.objects.get(title="Test Backfill")
        expected_name = incident.incident_number.lower()
        mock_slack_svc.rename_channel.assert_called_once_with("C_TEST", expected_name)
        assert mock_slack_svc.get_channel_info.call_count == 3

    def test_empty_title_returns_modal_error(self):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_TEST"}}

        handle_backfill_submission(ack, body, self._build_view(title=""), client)

        ack.assert_called_once()
        call_kwargs = ack.call_args[1]
        assert call_kwargs["response_action"] == "errors"
        client.chat_postMessage.assert_not_called()

    @patch(
        "firetower.slack_app.handlers.backfill_incident.get_or_create_user_from_slack_id"
    )
    def test_unknown_user_sends_dm(self, mock_get_user):
        mock_get_user.return_value = None

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_UNKNOWN"}}

        handle_backfill_submission(ack, body, self._build_view(), client)

        ack.assert_called_once_with()
        client.chat_postMessage.assert_called_once()
        msg = client.chat_postMessage.call_args[1]["text"]
        assert "Could not identify" in msg
