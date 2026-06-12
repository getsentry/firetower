from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.db import OperationalError

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.incidents.models import Incident, IncidentSeverity, Tag, TagType
from firetower.slack_app.bolt import handle_command
from firetower.slack_app.handlers.new_incident import (
    _build_new_incident_modal,
    _create_fallback_channel,
    handle_new_command,
    handle_new_incident_submission,
    handle_severity_action,
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

    @patch("firetower.slack_app.bolt.get_bolt_app")
    def test_new_modal_has_minimal_blocks(self, mock_get_bolt_app):
        """The /inc new modal should only require title + severity. Tag blocks
        are deferred to /inc mitigated and /inc resolved."""
        ack = MagicMock()
        body = {"trigger_id": "T12345"}
        command = {"text": "new"}
        respond = MagicMock()

        handle_new_command(ack, body, command, respond)

        view = mock_get_bolt_app.return_value.client.views_open.call_args[1]["view"]
        block_ids = [b["block_id"] for b in view["blocks"] if "block_id" in b]
        assert set(block_ids) == {
            "captain_block",
            "severity_block",
            "title_block",
            "description_block",
            "impact_summary_block",
            "options_block",
        }


def _get_options_block(modal: dict) -> dict:
    return next(b for b in modal["blocks"] if b.get("block_id") == "options_block")


def _option_values(modal: dict) -> set[str]:
    block = _get_options_block(modal)
    return {o["value"] for o in block["element"]["options"]}


def _initial_values(modal: dict) -> set[str]:
    block = _get_options_block(modal)
    return {o["value"] for o in block["element"].get("initial_options", [])}


class TestBuildNewIncidentModal:
    def test_skip_paging_option_present_for_p0(self):
        modal = _build_new_incident_modal(severity="P0")
        assert "skip_paging" in _option_values(modal)
        assert "skip_paging" in _initial_values(modal)

    def test_skip_paging_option_present_for_p1(self):
        modal = _build_new_incident_modal(severity="P1")
        assert "skip_paging" in _option_values(modal)

    def test_skip_paging_option_absent_for_p3(self):
        modal = _build_new_incident_modal(severity="P3")
        assert "skip_paging" not in _option_values(modal)

    def test_skip_paging_option_absent_by_default(self):
        modal = _build_new_incident_modal()
        assert "skip_paging" not in _option_values(modal)

    def test_private_option_always_present(self):
        modal = _build_new_incident_modal()
        assert "private" in _option_values(modal)

    def test_severity_block_has_dispatch_action(self):
        modal = _build_new_incident_modal()
        severity_block = next(
            b for b in modal["blocks"] if b.get("block_id") == "severity_block"
        )
        assert severity_block.get("dispatch_action") is True


class TestSeverityAction:
    def test_updates_view_with_skip_paging_for_p0(self):
        ack = MagicMock()
        client = MagicMock()
        body = {
            "view": {
                "id": "V_TEST",
                "callback_id": "new_incident_modal",
                "private_metadata": "",
                "state": {
                    "values": {
                        "severity_block": {
                            "severity": {
                                "selected_option": {"value": "P0"},
                            }
                        }
                    }
                },
            }
        }

        handle_severity_action(ack, body, client)

        ack.assert_called_once()
        client.views_update.assert_called_once()
        updated_view = client.views_update.call_args[1]["view"]
        assert "skip_paging" in _option_values(updated_view)

    def test_removes_skip_paging_for_p3(self):
        ack = MagicMock()
        client = MagicMock()
        body = {
            "view": {
                "id": "V_TEST",
                "callback_id": "new_incident_modal",
                "private_metadata": "",
                "state": {
                    "values": {
                        "severity_block": {
                            "severity": {
                                "selected_option": {"value": "P3"},
                            }
                        }
                    }
                },
            }
        }

        handle_severity_action(ack, body, client)

        ack.assert_called_once()
        updated_view = client.views_update.call_args[1]["view"]
        assert "skip_paging" not in _option_values(updated_view)

    def test_ignores_non_new_incident_modal(self):
        ack = MagicMock()
        client = MagicMock()
        body = {
            "view": {
                "id": "V_TEST",
                "callback_id": "other_modal",
                "state": {
                    "values": {
                        "severity_block": {
                            "severity": {
                                "selected_option": {"value": "P0"},
                            }
                        }
                    }
                },
            }
        }

        handle_severity_action(ack, body, client)

        ack.assert_called_once()
        client.views_update.assert_not_called()


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
                    "options_block": {"incident_options": {"selected_options": []}},
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
                    "options_block": {"incident_options": {"selected_options": []}},
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
                    "options_block": {
                        "incident_options": {"selected_options": [{"value": "private"}]}
                    },
                }
            },
        }

        handle_new_incident_submission(ack, body, view, client)

        client.chat_postMessage.assert_called_once()
        assert client.chat_postMessage.call_args[1]["channel"] == "U_TEST"

    @patch("firetower.incidents.serializers.on_incident_created")
    @patch("firetower.slack_app.handlers.new_incident.get_or_create_user_from_slack_id")
    def test_skip_paging_passed_to_hook(self, mock_get_user, mock_hook, settings):
        settings.HOOKS_ENABLED = True
        mock_get_user.return_value = self.user

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_TEST"}}
        view = {
            "state": {
                "values": {
                    "title_block": {"title": {"value": "Self-handled P1"}},
                    "severity_block": {
                        "severity": {
                            "selected_option": {"value": "P1"},
                        }
                    },
                    "description_block": {"description": {"value": ""}},
                    "options_block": {
                        "incident_options": {
                            "selected_options": [{"value": "skip_paging"}]
                        }
                    },
                }
            }
        }

        handle_new_incident_submission(ack, body, view, client)

        mock_hook.assert_called_once()
        incident = mock_hook.call_args[0][0]
        assert incident.title == "Self-handled P1"
        assert mock_hook.call_args[1]["skip_paging"] is True

    @patch("firetower.incidents.serializers.on_incident_created")
    @patch("firetower.slack_app.handlers.new_incident.get_or_create_user_from_slack_id")
    def test_skip_paging_default_false(self, mock_get_user, mock_hook, settings):
        settings.HOOKS_ENABLED = True
        mock_get_user.return_value = self.user

        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_TEST"}}
        view = {
            "state": {
                "values": {
                    "title_block": {"title": {"value": "Normal P1"}},
                    "severity_block": {
                        "severity": {
                            "selected_option": {"value": "P1"},
                        }
                    },
                    "description_block": {"description": {"value": ""}},
                    "options_block": {"incident_options": {"selected_options": []}},
                }
            }
        }

        handle_new_incident_submission(ack, body, view, client)

        mock_hook.assert_called_once()
        assert mock_hook.call_args[1]["skip_paging"] is False

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
                    "options_block": {"incident_options": {"selected_options": []}},
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
                    "options_block": {"incident_options": {"selected_options": []}},
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
    @patch("firetower.slack_app.handlers.new_incident._create_fallback_channel")
    @patch(
        "firetower.incidents.serializers.on_incident_created",
        side_effect=OperationalError("db is down"),
    )
    @patch("firetower.slack_app.handlers.new_incident.get_or_create_user_from_slack_id")
    def test_save_failure_creates_fallback_channel(
        self, mock_get_user, mock_hook, mock_fallback
    ):
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
                    "impact_summary_block": {
                        "impact_summary": {"value": "Users affected"}
                    },
                    "captain_block": {"captain_select": {"selected_user": "U_CAP"}},
                    "options_block": {"incident_options": {"selected_options": []}},
                    "impact_type_block": {"impact_type_tags": {"selected_options": []}},
                    "affected_service_block": {
                        "affected_service_tags": {"selected_options": []}
                    },
                    "affected_region_block": {
                        "affected_region_tags": {"selected_options": []}
                    },
                }
            }
        }

        handle_new_incident_submission(ack, body, view, client)

        mock_fallback.assert_called_once()
        call_args = mock_fallback.call_args
        assert call_args[0][0] is client
        assert call_args[0][1] == "U_TEST"
        form_data = call_args[0][2]
        assert form_data["title"] == "Test Incident"
        assert form_data["severity"] == "P1"
        assert form_data["description"] == "Description"
        assert form_data["captain_slack_id"] == "U_CAP"
        assert form_data["is_private"] is False

    @patch("firetower.slack_app.handlers.new_incident._create_fallback_channel")
    @patch(
        "firetower.slack_app.handlers.new_incident.get_or_create_user_from_slack_id",
        side_effect=OperationalError("db is down"),
    )
    def test_db_down_before_save_creates_fallback_channel(
        self, mock_get_user, mock_fallback
    ):
        ack = MagicMock()
        client = MagicMock()
        body = {"user": {"id": "U_TEST"}}
        view = {
            "state": {
                "values": {
                    "title_block": {"title": {"value": "DB Down Incident"}},
                    "severity_block": {
                        "severity": {
                            "selected_option": {"value": "P0"},
                        }
                    },
                    "description_block": {
                        "description": {"value": "Everything is on fire"}
                    },
                    "impact_summary_block": {"impact_summary": {"value": "All users"}},
                    "captain_block": {"captain_select": {"selected_user": None}},
                    "options_block": {"incident_options": {"selected_options": []}},
                    "impact_type_block": {"impact_type_tags": {"selected_options": []}},
                    "affected_service_block": {
                        "affected_service_tags": {"selected_options": []}
                    },
                    "affected_region_block": {
                        "affected_region_tags": {"selected_options": []}
                    },
                }
            }
        }

        handle_new_incident_submission(ack, body, view, client)

        mock_fallback.assert_called_once()
        form_data = mock_fallback.call_args[0][2]
        assert form_data["title"] == "DB Down Incident"
        assert form_data["severity"] == "P0"

    @pytest.mark.usefixtures("_enable_hooks")
    @patch("firetower.slack_app.handlers.new_incident._create_fallback_channel")
    @patch(
        "firetower.incidents.serializers.on_incident_created",
        side_effect=RuntimeError("boom"),
    )
    @patch("firetower.slack_app.handlers.new_incident.get_or_create_user_from_slack_id")
    def test_non_db_save_failure_sends_dm_without_fallback(
        self, mock_get_user, mock_hook, mock_fallback
    ):
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
                    "options_block": {"incident_options": {"selected_options": []}},
                }
            }
        }

        handle_new_incident_submission(ack, body, view, client)

        ack.assert_called_once_with()
        mock_fallback.assert_not_called()
        client.chat_postMessage.assert_called_once()
        msg = client.chat_postMessage.call_args[1]["text"]
        assert "Something went wrong" in msg


@pytest.mark.django_db
@patch("firetower.slack_app.handlers.new_incident.close_old_connections")
class TestTagOptions:
    def test_returns_matching_tags(self, _mock_close):
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

    def test_empty_query_returns_all(self, _mock_close):
        Tag.objects.create(name="us-east-1", type=TagType.AFFECTED_REGION)
        Tag.objects.create(name="eu-west-1", type=TagType.AFFECTED_REGION)

        ack = MagicMock()
        payload = {"action_id": "affected_region_tags", "value": ""}
        handle_tag_options(ack, payload)

        options = ack.call_args[1]["options"]
        assert len(options) == 2

    def test_unknown_action_id_returns_empty(self, _mock_close):
        ack = MagicMock()
        payload = {"action_id": "unknown_action", "value": ""}
        handle_tag_options(ack, payload)

        ack.assert_called_once_with(options=[])

    def test_filters_by_tag_type(self, _mock_close):
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
        }

    @patch("firetower.slack_app.handlers.new_incident._slack_service")
    def test_creates_channel_with_uuid_name(self, mock_slack_svc):
        mock_slack_svc.create_channel.return_value = "C_FALLBACK"
        mock_slack_svc.post_message.return_value = "1234.5678"
        mock_slack_svc.pin_message.return_value = True
        mock_slack_svc.build_channel_url.return_value = (
            "https://sentry.slack.com/archives/C_FALLBACK"
        )
        client = MagicMock()

        _create_fallback_channel(client, "U_REPORTER", self._base_form_data())

        # First create_channel call is the incident channel;
        # a second call may happen for the status channel (P0/P1).
        first_call = mock_slack_svc.create_channel.call_args_list[0]
        channel_name = first_call[0][0]
        prefix = f"{settings.PROJECT_KEY.lower()}-"
        assert channel_name.startswith(prefix)
        assert len(channel_name) == len(prefix) + 8  # prefix + 8 hex chars

    @patch("firetower.slack_app.handlers.new_incident._slack_service")
    def test_posts_and_pins_metadata(self, mock_slack_svc):
        mock_slack_svc.create_channel.return_value = "C_FALLBACK"
        mock_slack_svc.post_message.return_value = "1234.5678"
        mock_slack_svc.pin_message.return_value = True
        mock_slack_svc.build_channel_url.return_value = (
            "https://sentry.slack.com/archives/C_FALLBACK"
        )
        client = MagicMock()

        _create_fallback_channel(client, "U_REPORTER", self._base_form_data())

        first_call = mock_slack_svc.post_message.call_args_list[0]
        metadata_text = first_call[0][1]
        assert "Title: DB is on fire" in metadata_text
        assert "Severity: P1" in metadata_text
        assert "Description: Everything is broken" in metadata_text
        assert "Impact Summary: All users affected" in metadata_text
        assert "Captain: <@U_CAPTAIN>" in metadata_text
        assert "Reporter: <@U_REPORTER>" in metadata_text
        assert "Private: no" in metadata_text
        mock_slack_svc.pin_message.assert_called_once_with("C_FALLBACK", "1234.5678")

    @patch("firetower.slack_app.handlers.new_incident._slack_service")
    def test_posts_degraded_mode_warning(self, mock_slack_svc):
        mock_slack_svc.create_channel.return_value = "C_FALLBACK"
        mock_slack_svc.post_message.return_value = "1234.5678"
        mock_slack_svc.pin_message.return_value = True
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
        mock_slack_svc.post_message.return_value = "1234.5678"
        mock_slack_svc.pin_message.return_value = True
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
        mock_slack_svc.post_message.return_value = "1234.5678"
        mock_slack_svc.pin_message.return_value = True
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
        mock_slack_svc.post_message.return_value = "1234.5678"
        mock_slack_svc.pin_message.return_value = True
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
        mock_slack_svc.post_message.assert_not_called()

    @patch("firetower.slack_app.handlers.new_incident._slack_service")
    def test_private_incident_skips_feed_and_external_resources(
        self, mock_slack_svc, settings
    ):
        settings.SLACK = {
            **settings.SLACK,
            "INCIDENT_FEED_CHANNEL_ID": "C_FEED",
        }
        mock_slack_svc.create_channel.return_value = "C_FALLBACK"
        mock_slack_svc.post_message.return_value = "1234.5678"
        mock_slack_svc.pin_message.return_value = True
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
        mock_slack_svc.post_message.return_value = "1234.5678"
        mock_slack_svc.pin_message.return_value = True
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

    @patch("firetower.slack_app.handlers.new_incident.page_for_channel")
    @patch("firetower.slack_app.handlers.new_incident._slack_service")
    def test_skip_paging_skips_page_for_channel(self, mock_slack_svc, mock_page):
        mock_slack_svc.create_channel.return_value = "C_FALLBACK"
        mock_slack_svc.post_message.return_value = "1234.5678"
        mock_slack_svc.pin_message.return_value = True
        mock_slack_svc.build_channel_url.return_value = (
            "https://sentry.slack.com/archives/C_FALLBACK"
        )
        client = MagicMock()

        form_data = self._base_form_data()
        form_data["skip_paging"] = True

        _create_fallback_channel(client, "U_REPORTER", form_data)

        mock_page.assert_called_once()
        assert mock_page.call_args[1]["skip_paging"] is True
