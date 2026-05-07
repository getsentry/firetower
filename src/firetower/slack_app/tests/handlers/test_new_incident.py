from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.incidents.models import Incident, IncidentSeverity, Tag, TagType
from firetower.slack_app.bolt import handle_command
from firetower.slack_app.handlers.new_incident import (
    _create_fallback_channel,
    handle_new_command,
    handle_new_incident_submission,
    handle_tag_options,
)


@pytest.mark.django_db
class TestNewSubcommandRouting:
    def _make_body(self, text="", command="/ft"):
        return {"text": text, "command": command}

    def _make_command(self, command="/ft", text=""):
        return {"command": command, "text": text}

    @patch("firetower.slack_app.bolt.get_bolt_app")
    @patch("firetower.slack_app.bolt.statsd")
    def test_new_subcommand_routes_correctly(self, mock_statsd, mock_get_bolt_app):
        ack = MagicMock()
        respond = MagicMock()
        body = self._make_body(text="new")
        body["trigger_id"] = "T12345"
        command = self._make_command()

        handle_command(ack=ack, body=body, command=command, respond=respond)

        ack.assert_called_once()
        mock_get_bolt_app.return_value.client.views_open.assert_called_once()


@pytest.mark.django_db
class TestNewIncidentModal:
    @patch("firetower.slack_app.bolt.get_bolt_app")
    def test_new_opens_modal(self, mock_get_bolt_app):
        ack = MagicMock()
        body = {"trigger_id": "T12345"}
        command = {"text": "new"}
        respond = MagicMock()

        handle_new_command(ack, body, command, respond)

        ack.assert_called_once()
        mock_get_bolt_app.return_value.client.views_open.assert_called_once()
        view = mock_get_bolt_app.return_value.client.views_open.call_args[1]["view"]
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

    @patch("firetower.slack_app.handlers.new_incident._slack_service")
    @patch("firetower.incidents.serializers.on_incident_created")
    @patch("firetower.slack_app.handlers.new_incident.get_or_create_user_from_slack_id")
    def test_posts_to_invoking_channel(self, mock_get_user, mock_hook, mock_slack_svc):
        mock_get_user.return_value = self.user

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_TEST"}}
        view = {
            "private_metadata": "C_INVOKE",
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
            },
        }

        handle_new_incident_submission(ack, body, view, client)

        assert client.chat_postMessage.call_count == 2
        channels = [c[1]["channel"] for c in client.chat_postMessage.call_args_list]
        assert "C_INVOKE" in channels
        mock_slack_svc.join_channel.assert_called_once_with("C_INVOKE")

    @patch("firetower.slack_app.handlers.new_incident._slack_service")
    @patch("firetower.incidents.serializers.on_incident_created")
    @patch("firetower.slack_app.handlers.new_incident.get_or_create_user_from_slack_id")
    def test_private_incident_skips_invoking_channel(
        self, mock_get_user, mock_hook, mock_slack_svc
    ):
        mock_get_user.return_value = self.user

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_TEST"}}
        view = {
            "private_metadata": "C_INVOKE",
            "state": {
                "values": {
                    "title_block": {"title": {"value": "Test Incident"}},
                    "severity_block": {
                        "severity": {
                            "selected_option": {"value": "P1"},
                        }
                    },
                    "description_block": {"description": {"value": "Description"}},
                    "private_block": {
                        "is_private": {"selected_options": [{"value": "private"}]}
                    },
                }
            },
        }

        handle_new_incident_submission(ack, body, view, client)

        client.chat_postMessage.assert_called_once()
        assert client.chat_postMessage.call_args[1]["channel"] == "U_TEST"

    def test_empty_title_returns_modal_error(self):
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
    def test_unknown_user_sends_dm(self, mock_get_user):
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

        ack.assert_called_once_with()
        client.chat_postMessage.assert_called_once()
        msg = client.chat_postMessage.call_args[1]["text"]
        assert "Could not identify" in msg

    @pytest.fixture(autouse=False)
    def _enable_hooks(self, settings):
        settings.HOOKS_ENABLED = True

    @pytest.mark.usefixtures("_enable_hooks")
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
        assert "Slack channel manually" in msg


@pytest.mark.django_db
class TestTagOptions:
    def test_returns_matching_tags(self):
        Tag.objects.create(name="us-east-1", type=TagType.AFFECTED_REGION)
        Tag.objects.create(name="us-west-2", type=TagType.AFFECTED_REGION)
        Tag.objects.create(name="eu-west-1", type=TagType.AFFECTED_REGION)

        ack = MagicMock()
        payload = {"action_id": "affected_region_tags", "value": "us"}
        handle_tag_options(ack, payload)

        ack.assert_called_once()
        options = ack.call_args[1]["options"]
        assert len(options) == 2
        names = {o["text"]["text"] for o in options}
        assert names == {"us-east-1", "us-west-2"}

    def test_empty_query_returns_all(self):
        Tag.objects.create(name="us-east-1", type=TagType.AFFECTED_REGION)
        Tag.objects.create(name="eu-west-1", type=TagType.AFFECTED_REGION)

        ack = MagicMock()
        payload = {"action_id": "affected_region_tags", "value": ""}
        handle_tag_options(ack, payload)

        options = ack.call_args[1]["options"]
        assert len(options) == 2

    def test_unknown_action_id_returns_empty(self):
        ack = MagicMock()
        payload = {"action_id": "unknown_action", "value": ""}
        handle_tag_options(ack, payload)

        ack.assert_called_once_with(options=[])

    def test_filters_by_tag_type(self):
        Tag.objects.create(name="us-east-1", type=TagType.AFFECTED_REGION)
        Tag.objects.create(name="api", type=TagType.AFFECTED_SERVICE)

        ack = MagicMock()
        payload = {"action_id": "affected_region_tags", "value": ""}
        handle_tag_options(ack, payload)

        options = ack.call_args[1]["options"]
        assert len(options) == 1
        assert options[0]["text"]["text"] == "us-east-1"


class TestFallbackChannel:
    def _base_form_data(self):
        return {
            "title": "DB is on fire",
            "severity": "P1",
            "description": "Everything is broken",
            "impact_summary": "All users affected",
            "captain_slack_id": "U_CAPTAIN",
            "is_private": False,
            "impact_type_tags": ["Degraded Service"],
            "affected_service_tags": ["api"],
            "affected_region_tags": ["us-east-1"],
        }

    @patch("firetower.slack_app.handlers.new_incident._slack_service")
    def test_creates_channel_with_uuid_name(self, mock_slack_svc):
        mock_slack_svc.create_channel.return_value = "C_FALLBACK"
        mock_slack_svc.post_message_return_ts.return_value = "1234.5678"
        mock_slack_svc.pin_message.return_value = True
        mock_slack_svc.post_message.return_value = True
        mock_slack_svc.build_channel_url.return_value = (
            "https://sentry.slack.com/archives/C_FALLBACK"
        )
        client = MagicMock()

        _create_fallback_channel(client, "U_REPORTER", self._base_form_data())

        # First create_channel call is the incident channel;
        # a second call may happen for the status channel (P0/P1).
        first_call = mock_slack_svc.create_channel.call_args_list[0]
        channel_name = first_call[0][0]
        assert channel_name.startswith("inc-")
        assert len(channel_name) == 12  # "inc-" + 8 hex chars

    @patch("firetower.slack_app.handlers.new_incident._slack_service")
    def test_posts_and_pins_metadata(self, mock_slack_svc):
        mock_slack_svc.create_channel.return_value = "C_FALLBACK"
        mock_slack_svc.post_message_return_ts.return_value = "1234.5678"
        mock_slack_svc.pin_message.return_value = True
        mock_slack_svc.post_message.return_value = True
        mock_slack_svc.build_channel_url.return_value = (
            "https://sentry.slack.com/archives/C_FALLBACK"
        )
        client = MagicMock()

        _create_fallback_channel(client, "U_REPORTER", self._base_form_data())

        mock_slack_svc.post_message_return_ts.assert_called_once()
        metadata_text = mock_slack_svc.post_message_return_ts.call_args[0][1]
        assert "Title: DB is on fire" in metadata_text
        assert "Severity: P1" in metadata_text
        assert "Description: Everything is broken" in metadata_text
        assert "Impact Summary: All users affected" in metadata_text
        assert "Captain: <@U_CAPTAIN>" in metadata_text
        assert "Reporter: <@U_REPORTER>" in metadata_text
        assert "Private: no" in metadata_text
        assert "Impact Types: Degraded Service" in metadata_text
        assert "Affected Services: api" in metadata_text
        assert "Affected Regions: us-east-1" in metadata_text
        mock_slack_svc.pin_message.assert_called_once_with("C_FALLBACK", "1234.5678")

    @patch("firetower.slack_app.handlers.new_incident._slack_service")
    def test_posts_degraded_mode_warning(self, mock_slack_svc):
        mock_slack_svc.create_channel.return_value = "C_FALLBACK"
        mock_slack_svc.post_message_return_ts.return_value = "1234.5678"
        mock_slack_svc.pin_message.return_value = True
        mock_slack_svc.post_message.return_value = True
        mock_slack_svc.build_channel_url.return_value = (
            "https://sentry.slack.com/archives/C_FALLBACK"
        )
        client = MagicMock()

        _create_fallback_channel(client, "U_REPORTER", self._base_form_data())

        warning_calls = [
            c
            for c in mock_slack_svc.post_message.call_args_list
            if "degraded mode" in str(c)
        ]
        assert len(warning_calls) >= 1

    @patch("firetower.slack_app.handlers.new_incident._slack_service")
    def test_posts_guide_message(self, mock_slack_svc, settings):
        settings.SLACK = {
            **settings.SLACK,
            "INCIDENT_GUIDE_MESSAGE": "Welcome to incident response!",
        }
        mock_slack_svc.create_channel.return_value = "C_FALLBACK"
        mock_slack_svc.post_message_return_ts.return_value = "1234.5678"
        mock_slack_svc.pin_message.return_value = True
        mock_slack_svc.post_message.return_value = True
        mock_slack_svc.build_channel_url.return_value = (
            "https://sentry.slack.com/archives/C_FALLBACK"
        )
        client = MagicMock()

        _create_fallback_channel(client, "U_REPORTER", self._base_form_data())

        guide_calls = [
            c
            for c in mock_slack_svc.post_message.call_args_list
            if "Welcome to incident response!" in str(c)
        ]
        assert len(guide_calls) == 1

    @patch("firetower.slack_app.handlers.new_incident._slack_service")
    def test_invites_captain_reporter_and_always_invited(
        self, mock_slack_svc, settings
    ):
        settings.SLACK = {**settings.SLACK, "ALWAYS_INVITED_IDS": ["U_ALWAYS"]}
        mock_slack_svc.create_channel.return_value = "C_FALLBACK"
        mock_slack_svc.post_message_return_ts.return_value = "1234.5678"
        mock_slack_svc.pin_message.return_value = True
        mock_slack_svc.post_message.return_value = True
        mock_slack_svc.build_channel_url.return_value = (
            "https://sentry.slack.com/archives/C_FALLBACK"
        )
        client = MagicMock()

        _create_fallback_channel(client, "U_REPORTER", self._base_form_data())

        mock_slack_svc.invite_to_channel.assert_any_call(
            "C_FALLBACK", ["U_CAPTAIN", "U_REPORTER", "U_ALWAYS"]
        )

    @patch("firetower.slack_app.handlers.new_incident._slack_service")
    def test_dms_user_with_channel_link(self, mock_slack_svc):
        mock_slack_svc.create_channel.return_value = "C_FALLBACK"
        mock_slack_svc.post_message_return_ts.return_value = "1234.5678"
        mock_slack_svc.pin_message.return_value = True
        mock_slack_svc.post_message.return_value = True
        mock_slack_svc.build_channel_url.return_value = (
            "https://sentry.slack.com/archives/C_FALLBACK"
        )
        client = MagicMock()

        _create_fallback_channel(client, "U_REPORTER", self._base_form_data())

        client.chat_postMessage.assert_called_once()
        dm_text = client.chat_postMessage.call_args[1]["text"]
        assert "degraded mode" in dm_text
        assert "<#C_FALLBACK>" in dm_text

    @patch("firetower.slack_app.handlers.new_incident._slack_service")
    def test_channel_creation_failure_sends_manual_dm(self, mock_slack_svc):
        mock_slack_svc.create_channel.return_value = None
        client = MagicMock()

        _create_fallback_channel(client, "U_REPORTER", self._base_form_data())

        client.chat_postMessage.assert_called_once()
        dm_text = client.chat_postMessage.call_args[1]["text"]
        assert "Slack channel manually" in dm_text
        mock_slack_svc.post_message_return_ts.assert_not_called()

    @patch("firetower.slack_app.handlers.new_incident._slack_service")
    def test_private_incident_skips_feed_and_external_resources(
        self, mock_slack_svc, settings
    ):
        settings.SLACK = {
            **settings.SLACK,
            "INCIDENT_FEED_CHANNEL_ID": "C_FEED",
        }
        mock_slack_svc.create_channel.return_value = "C_FALLBACK"
        mock_slack_svc.post_message_return_ts.return_value = "1234.5678"
        mock_slack_svc.pin_message.return_value = True
        mock_slack_svc.post_message.return_value = True
        mock_slack_svc.build_channel_url.return_value = (
            "https://sentry.slack.com/archives/C_FALLBACK"
        )
        client = MagicMock()

        form_data = self._base_form_data()
        form_data["is_private"] = True

        _create_fallback_channel(client, "U_REPORTER", form_data)

        # Only one create_channel call (the main channel, no status channel)
        assert mock_slack_svc.create_channel.call_count == 1
        # No feed channel message
        feed_calls = [
            c for c in mock_slack_svc.post_message.call_args_list if c[0][0] == "C_FEED"
        ]
        assert len(feed_calls) == 0

    @patch("firetower.slack_app.handlers.new_incident._slack_service")
    def test_non_private_posts_to_feed_channel(self, mock_slack_svc, settings):
        settings.SLACK = {
            **settings.SLACK,
            "INCIDENT_FEED_CHANNEL_ID": "C_FEED",
        }
        mock_slack_svc.create_channel.return_value = "C_FALLBACK"
        mock_slack_svc.post_message_return_ts.return_value = "1234.5678"
        mock_slack_svc.pin_message.return_value = True
        mock_slack_svc.post_message.return_value = True
        mock_slack_svc.build_channel_url.return_value = (
            "https://sentry.slack.com/archives/C_FALLBACK"
        )
        client = MagicMock()

        _create_fallback_channel(client, "U_REPORTER", self._base_form_data())

        feed_calls = [
            c for c in mock_slack_svc.post_message.call_args_list if c[0][0] == "C_FEED"
        ]
        assert len(feed_calls) == 1
        assert "degraded mode" in feed_calls[0][0][1]
        assert "DB is on fire" in feed_calls[0][0][1]
