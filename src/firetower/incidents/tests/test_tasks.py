from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, call, patch

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from django_q.models import Schedule

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.incidents.models import (
    ActionItem,
    ActionItemStatus,
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from firetower.incidents.tasks import (
    STATUSPAGE_FOLLOWUP_REMINDER_MESSAGE,
    STATUSPAGE_REMINDER_MESSAGE,
    datadog_log,
    schedule_demo,
    send_action_item_reminder,
    send_statuspage_followup_reminder,
    send_statuspage_reminder,
)


class TestDatadogLogTaskName:
    @patch("firetower.incidents.tasks.decorators.statsd")
    def test_replaces_invalid_chars_with_underscore(self, mock_statsd):
        def f_with_bad_chars() -> None:
            pass

        f_with_bad_chars.__name__ = "task with spaces & symbols!"
        wrapped = datadog_log(f_with_bad_chars)
        wrapped()

        expected_tags = ["task:task_with_spaces___symbols_"]
        mock_statsd.increment.assert_any_call("django_q.task.run", 1, expected_tags)

    @patch("firetower.incidents.tasks.decorators.statsd")
    def test_preserves_alphanumerics_dash_underscore_dot_slash(self, mock_statsd):
        def f() -> None:
            pass

        f.__name__ = "namespace/sub-task_v1.2"
        wrapped = datadog_log(f)
        wrapped()

        expected_tags = ["task:namespace/sub-task_v1.2"]
        mock_statsd.increment.assert_any_call("django_q.task.run", 1, expected_tags)

    @patch("firetower.incidents.tasks.decorators.statsd")
    def test_replaces_consecutive_invalid_chars_individually(self, mock_statsd):
        def f() -> None:
            pass

        f.__name__ = "a@@b"
        wrapped = datadog_log(f)
        wrapped()

        expected_tags = ["task:a__b"]
        mock_statsd.increment.assert_any_call("django_q.task.run", 1, expected_tags)


class TestDatadogLogStatsdIncrements:
    @patch("firetower.incidents.tasks.decorators.statsd")
    def test_increments_run_and_success_on_normal_completion(self, mock_statsd):
        def f() -> None:
            pass

        f.__name__ = "ok_task"
        wrapped = datadog_log(f)
        wrapped()

        tags = ["task:ok_task"]
        assert mock_statsd.increment.call_args_list == [
            call("django_q.task.run", 1, tags),
            call("django_q.task.success", 1, tags),
        ]

    @patch("firetower.incidents.tasks.decorators.statsd")
    def test_increments_run_and_error_when_function_raises(self, mock_statsd):
        def f() -> None:
            raise ValueError("boom")

        f.__name__ = "broken_task"
        wrapped = datadog_log(f)
        with pytest.raises(ValueError):
            wrapped()

        tags = ["task:broken_task"]
        assert mock_statsd.increment.call_args_list == [
            call("django_q.task.run", 1, tags),
            call("django_q.task.error", 1, tags),
        ]

    @patch("firetower.incidents.tasks.decorators.statsd")
    def test_does_not_increment_success_when_function_raises(self, mock_statsd):
        def f() -> None:
            raise RuntimeError("nope")

        f.__name__ = "failing_task"
        wrapped = datadog_log(f)
        with pytest.raises(RuntimeError):
            wrapped()

        success_calls = [
            c
            for c in mock_statsd.increment.call_args_list
            if c.args[0] == "django_q.task.success"
        ]
        assert success_calls == []

    @patch("firetower.incidents.tasks.decorators.statsd")
    def test_re_raises_exception_from_wrapped_function(self, mock_statsd):
        def f() -> None:
            raise ValueError("should propagate")

        f.__name__ = "raises"
        wrapped = datadog_log(f)

        with pytest.raises(ValueError, match="should propagate"):
            wrapped()


class TestScheduleDemoPrivateIncident:
    @patch("firetower.incidents.tasks.decorators.statsd")
    @patch("firetower.incidents.tasks.Incident")
    def test_masks_title_for_private_incident(self, mock_incident_cls, mock_statsd):
        mock_incident = MagicMock()
        mock_incident.id = 42
        mock_incident.title = "Secret outage details"
        mock_incident.is_private = True
        mock_incident_cls.objects.order_by.return_value.first.return_value = (
            mock_incident
        )

        with patch("firetower.incidents.tasks.logger") as mock_logger:
            schedule_demo.__wrapped__()

        logged = mock_logger.info.call_args[0][0]
        assert "Private Incident" in logged
        assert "Secret outage details" not in logged

    @patch("firetower.incidents.tasks.decorators.statsd")
    @patch("firetower.incidents.tasks.Incident")
    def test_shows_title_for_public_incident(self, mock_incident_cls, mock_statsd):
        mock_incident = MagicMock()
        mock_incident.id = 43
        mock_incident.title = "Public outage"
        mock_incident.is_private = False
        mock_incident_cls.objects.order_by.return_value.first.return_value = (
            mock_incident
        )

        with patch("firetower.incidents.tasks.logger") as mock_logger:
            schedule_demo.__wrapped__()

        logged = mock_logger.info.call_args[0][0]
        assert "Public outage" in logged


@pytest.mark.django_db
class TestSendStatuspageReminder:
    CONFIGURED_DELAY_MINUTES = 15

    @pytest.fixture(autouse=True)
    def _configure_statuspage(self):
        statuspage_settings = {
            "API_KEY": "test",
            "PAGE_ID": "test",
            "URL": "https://test.statuspage.io/",
            "INITIAL_REMINDER_DELAY_MINUTES": self.CONFIGURED_DELAY_MINUTES,
            "WARNING_BUFFER_MINUTES": 0,
        }
        with patch.object(settings, "STATUSPAGE", statuspage_settings):
            yield

    def _make_incident(self, **kwargs):
        defaults = {
            "title": "Test Incident",
            "status": IncidentStatus.ACTIVE,
            "severity": IncidentSeverity.P0,
        }
        defaults.update(kwargs)
        return Incident.objects.create(**defaults)

    def _make_link(
        self, incident, link_type, url="https://sentry.slack.com/archives/C12345"
    ):
        return ExternalLink.objects.create(
            incident=incident,
            type=link_type,
            url=url,
        )

    def test_posts_reminder_for_p0_without_statuspage(self):
        now = datetime.now(tz=UTC)
        incident = self._make_incident(severity=IncidentSeverity.P0)
        self._make_link(incident, ExternalLinkType.SLACK)

        mock_slack = MagicMock()
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        with (
            patch(
                "firetower.incidents.tasks.statuspage.SlackService",
                return_value=mock_slack,
            ),
            patch("firetower.incidents.tasks.statuspage.timezone") as mock_tz,
        ):
            mock_tz.now.return_value = now
            send_statuspage_reminder(incident.id)

        incident.refresh_from_db()
        slo_deadline = incident.created_at + timedelta(
            minutes=self.CONFIGURED_DELAY_MINUTES
        )
        minutes_remaining = max(0, int((slo_deadline - now).total_seconds() / 60))
        expected_msg = STATUSPAGE_REMINDER_MESSAGE.format(
            severity="P0",
            slash_command=settings.SLACK.get("SLASH_COMMAND", "/inc"),
            slo_minutes=self.CONFIGURED_DELAY_MINUTES,
            minutes_remaining=minutes_remaining,
            ic_mention="",
        )
        mock_slack.post_message.assert_called_once_with("C12345", expected_msg)

    def test_prefers_status_channel_over_main_channel(self):
        now = datetime.now(tz=UTC)
        incident = self._make_incident(severity=IncidentSeverity.P0)
        self._make_link(incident, ExternalLinkType.SLACK)
        self._make_link(
            incident,
            ExternalLinkType.SLACK_STATUS,
            url="https://sentry.slack.com/archives/C99999",
        )

        mock_slack = MagicMock()
        mock_slack.parse_channel_id_from_url.return_value = "C99999"

        with (
            patch(
                "firetower.incidents.tasks.statuspage.SlackService",
                return_value=mock_slack,
            ),
            patch("firetower.incidents.tasks.statuspage.timezone") as mock_tz,
        ):
            mock_tz.now.return_value = now
            send_statuspage_reminder(incident.id)

        mock_slack.parse_channel_id_from_url.assert_called_once_with(
            "https://sentry.slack.com/archives/C99999"
        )
        mock_slack.post_message.assert_called_once()

    def test_uses_scheduled_at_for_slo_deadline(self):
        now = datetime.now(tz=UTC)
        scheduled_at = now - timedelta(minutes=5)
        incident = self._make_incident(severity=IncidentSeverity.P0)
        self._make_link(incident, ExternalLinkType.SLACK)

        mock_slack = MagicMock()
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        with (
            patch(
                "firetower.incidents.tasks.statuspage.SlackService",
                return_value=mock_slack,
            ),
            patch("firetower.incidents.tasks.statuspage.timezone") as mock_tz,
        ):
            mock_tz.now.return_value = now
            send_statuspage_reminder(incident.id, scheduled_at=scheduled_at.isoformat())

        slo_deadline = scheduled_at + timedelta(minutes=self.CONFIGURED_DELAY_MINUTES)
        minutes_remaining = max(0, int((slo_deadline - now).total_seconds() / 60))
        expected_msg = STATUSPAGE_REMINDER_MESSAGE.format(
            severity="P0",
            slash_command=settings.SLACK.get("SLASH_COMMAND", "/inc"),
            slo_minutes=self.CONFIGURED_DELAY_MINUTES,
            minutes_remaining=minutes_remaining,
            ic_mention="",
        )
        mock_slack.post_message.assert_called_once_with("C12345", expected_msg)

    def test_posts_reminder_for_p1_without_statuspage(self):
        incident = self._make_incident(severity=IncidentSeverity.P1)
        self._make_link(incident, ExternalLinkType.SLACK)

        mock_slack = MagicMock()
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        with patch(
            "firetower.incidents.tasks.statuspage.SlackService", return_value=mock_slack
        ):
            send_statuspage_reminder(incident.id)

        mock_slack.post_message.assert_called_once()

    def test_skips_when_statuspage_exists(self):
        incident = self._make_incident(severity=IncidentSeverity.P0)
        self._make_link(incident, ExternalLinkType.SLACK)
        self._make_link(
            incident,
            ExternalLinkType.STATUSPAGE,
            url="https://manage.statuspage.io/incidents/abc123",
        )

        mock_slack = MagicMock()
        with patch(
            "firetower.incidents.tasks.statuspage.SlackService", return_value=mock_slack
        ):
            send_statuspage_reminder(incident.id)

        mock_slack.post_message.assert_not_called()

    def test_skips_for_p2_severity(self):
        incident = self._make_incident(severity=IncidentSeverity.P2)
        self._make_link(incident, ExternalLinkType.SLACK)

        mock_slack = MagicMock()
        with patch(
            "firetower.incidents.tasks.statuspage.SlackService", return_value=mock_slack
        ):
            send_statuspage_reminder(incident.id)

        mock_slack.post_message.assert_not_called()

    def test_skips_for_done_status(self):
        incident = self._make_incident(
            severity=IncidentSeverity.P0, status=IncidentStatus.DONE
        )
        self._make_link(incident, ExternalLinkType.SLACK)

        mock_slack = MagicMock()
        with patch(
            "firetower.incidents.tasks.statuspage.SlackService", return_value=mock_slack
        ):
            send_statuspage_reminder(incident.id)

        mock_slack.post_message.assert_not_called()

    def test_skips_for_canceled_status(self):
        incident = self._make_incident(
            severity=IncidentSeverity.P0, status=IncidentStatus.CANCELED
        )
        self._make_link(incident, ExternalLinkType.SLACK)

        mock_slack = MagicMock()
        with patch(
            "firetower.incidents.tasks.statuspage.SlackService", return_value=mock_slack
        ):
            send_statuspage_reminder(incident.id)

        mock_slack.post_message.assert_not_called()

    def test_posts_for_mitigated_status(self):
        incident = self._make_incident(
            severity=IncidentSeverity.P0, status=IncidentStatus.MITIGATED
        )
        self._make_link(incident, ExternalLinkType.SLACK)

        mock_slack = MagicMock()
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        with patch(
            "firetower.incidents.tasks.statuspage.SlackService", return_value=mock_slack
        ):
            send_statuspage_reminder(incident.id)

        mock_slack.post_message.assert_called_once()

    def test_skips_when_delay_not_configured(self):
        incident = self._make_incident(severity=IncidentSeverity.P0)
        self._make_link(incident, ExternalLinkType.SLACK)

        mock_slack = MagicMock()
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        with (
            patch(
                "firetower.incidents.tasks.statuspage.SlackService",
                return_value=mock_slack,
            ),
            patch.object(
                settings,
                "STATUSPAGE",
                {
                    "API_KEY": "test",
                    "PAGE_ID": "test",
                    "URL": "https://test.statuspage.io/",
                    "INITIAL_REMINDER_DELAY_MINUTES": None,
                    "WARNING_BUFFER_MINUTES": 0,
                },
            ),
        ):
            send_statuspage_reminder(incident.id)

        mock_slack.post_message.assert_not_called()

    def test_skips_when_incident_not_found(self):
        mock_slack = MagicMock()
        with patch(
            "firetower.incidents.tasks.statuspage.SlackService", return_value=mock_slack
        ):
            send_statuspage_reminder(99999)

        mock_slack.post_message.assert_not_called()

    def test_skips_when_no_slack_link(self):
        incident = self._make_incident(severity=IncidentSeverity.P0)

        mock_slack = MagicMock()
        with patch(
            "firetower.incidents.tasks.statuspage.SlackService", return_value=mock_slack
        ):
            send_statuspage_reminder(incident.id)

        mock_slack.post_message.assert_not_called()

    def test_skips_when_channel_id_not_parsed(self):
        incident = self._make_incident(severity=IncidentSeverity.P0)
        self._make_link(incident, ExternalLinkType.SLACK, url="https://bad-url")

        mock_slack = MagicMock()
        mock_slack.parse_channel_id_from_url.return_value = None

        with patch(
            "firetower.incidents.tasks.statuspage.SlackService", return_value=mock_slack
        ):
            send_statuspage_reminder(incident.id)

        mock_slack.post_message.assert_not_called()

    def test_includes_ic_slack_mention(self):
        captain = User.objects.create_user(
            username="captain@example.com", email="captain@example.com"
        )
        ExternalProfile.objects.create(
            user=captain, type=ExternalProfileType.SLACK, external_id="U_CAPTAIN"
        )
        incident = self._make_incident(severity=IncidentSeverity.P0, captain=captain)
        self._make_link(incident, ExternalLinkType.SLACK)

        mock_slack = MagicMock()
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        with patch(
            "firetower.incidents.tasks.statuspage.SlackService", return_value=mock_slack
        ):
            send_statuspage_reminder(incident.id)

        msg = mock_slack.post_message.call_args[0][1]
        assert "\n<@U_CAPTAIN>" in msg

    def test_omits_ic_without_slack_profile(self):
        captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Jane",
            last_name="Doe",
        )
        incident = self._make_incident(severity=IncidentSeverity.P0, captain=captain)
        self._make_link(incident, ExternalLinkType.SLACK)

        mock_slack = MagicMock()
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        with patch(
            "firetower.incidents.tasks.statuspage.SlackService", return_value=mock_slack
        ):
            send_statuspage_reminder(incident.id)

        msg = mock_slack.post_message.call_args[0][1]
        assert "Jane Doe" not in msg


@pytest.mark.django_db
class TestSendStatuspageFollowupReminder:
    CONFIGURED_FOLLOWUP_DELAY_MINUTES = 30
    CONFIGURED_WARNING_BUFFER_MINUTES = 5

    @pytest.fixture(autouse=True)
    def _configure_statuspage(self):
        statuspage_settings = {
            "API_KEY": "test",
            "PAGE_ID": "test",
            "URL": "https://test.statuspage.io/",
            "INITIAL_REMINDER_DELAY_MINUTES": 15,
            "FOLLOWUP_REMINDER_DELAY_MINUTES": self.CONFIGURED_FOLLOWUP_DELAY_MINUTES,
            "WARNING_BUFFER_MINUTES": self.CONFIGURED_WARNING_BUFFER_MINUTES,
        }
        with patch.object(settings, "STATUSPAGE", statuspage_settings):
            yield

    def _make_incident(self, **kwargs):
        defaults = {
            "title": "Test Incident",
            "status": IncidentStatus.ACTIVE,
            "severity": IncidentSeverity.P0,
        }
        defaults.update(kwargs)
        return Incident.objects.create(**defaults)

    def _make_link(
        self, incident, link_type, url="https://sentry.slack.com/archives/C12345"
    ):
        return ExternalLink.objects.create(
            incident=incident,
            type=link_type,
            url=url,
        )

    def test_posts_followup_reminder_when_statuspage_exists(self):
        incident = self._make_incident(severity=IncidentSeverity.P0)
        self._make_link(incident, ExternalLinkType.SLACK)
        self._make_link(
            incident,
            ExternalLinkType.STATUSPAGE,
            url="https://manage.statuspage.io/incidents/abc123",
        )

        mock_slack = MagicMock()
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        offset_minutes = (
            self.CONFIGURED_FOLLOWUP_DELAY_MINUTES
            - self.CONFIGURED_WARNING_BUFFER_MINUTES
        )
        scheduled_at = now - timedelta(minutes=offset_minutes)

        with (
            patch(
                "firetower.incidents.tasks.statuspage.SlackService",
                return_value=mock_slack,
            ),
            patch("firetower.incidents.tasks.statuspage.timezone") as mock_tz,
            patch(
                "firetower.incidents.tasks.statuspage.get_statuspage_followup_reminder_delay_minutes",
                return_value=self.CONFIGURED_FOLLOWUP_DELAY_MINUTES,
            ),
        ):
            mock_tz.now.return_value = now
            send_statuspage_followup_reminder(
                incident.id, scheduled_at=scheduled_at.isoformat()
            )

        expected_msg = STATUSPAGE_FOLLOWUP_REMINDER_MESSAGE.format(
            severity="P0",
            slash_command=settings.SLACK.get("SLASH_COMMAND", "/inc"),
            minutes_until_due=self.CONFIGURED_WARNING_BUFFER_MINUTES,
            ic_mention="",
        )
        mock_slack.post_message.assert_called_once_with("C12345", expected_msg)

    def test_reschedules_after_posting(self):
        incident = self._make_incident(severity=IncidentSeverity.P0)
        self._make_link(incident, ExternalLinkType.SLACK)
        self._make_link(
            incident,
            ExternalLinkType.STATUSPAGE,
            url="https://manage.statuspage.io/incidents/abc123",
        )

        mock_slack = MagicMock()
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        with (
            patch(
                "firetower.incidents.tasks.statuspage.SlackService",
                return_value=mock_slack,
            ),
            patch(
                "firetower.incidents.tasks.statuspage.get_statuspage_followup_reminder_delay_minutes",
                return_value=self.CONFIGURED_FOLLOWUP_DELAY_MINUTES,
            ),
        ):
            send_statuspage_followup_reminder(incident.id)

        assert Schedule.objects.filter(
            name=f"statuspage_followup_reminder_{incident.id}"
        ).exists()

    def test_skips_when_no_statuspage(self):
        incident = self._make_incident(severity=IncidentSeverity.P0)
        self._make_link(incident, ExternalLinkType.SLACK)

        mock_slack = MagicMock()
        with patch(
            "firetower.incidents.tasks.statuspage.SlackService", return_value=mock_slack
        ):
            send_statuspage_followup_reminder(incident.id)

        mock_slack.post_message.assert_not_called()

    def test_skips_for_p2_severity(self):
        incident = self._make_incident(severity=IncidentSeverity.P2)
        self._make_link(incident, ExternalLinkType.SLACK)
        self._make_link(
            incident,
            ExternalLinkType.STATUSPAGE,
            url="https://manage.statuspage.io/incidents/abc123",
        )

        mock_slack = MagicMock()
        with patch(
            "firetower.incidents.tasks.statuspage.SlackService", return_value=mock_slack
        ):
            send_statuspage_followup_reminder(incident.id)

        mock_slack.post_message.assert_not_called()

    def test_skips_for_done_status(self):
        incident = self._make_incident(
            severity=IncidentSeverity.P0, status=IncidentStatus.DONE
        )
        self._make_link(incident, ExternalLinkType.SLACK)
        self._make_link(
            incident,
            ExternalLinkType.STATUSPAGE,
            url="https://manage.statuspage.io/incidents/abc123",
        )

        mock_slack = MagicMock()
        with patch(
            "firetower.incidents.tasks.statuspage.SlackService", return_value=mock_slack
        ):
            send_statuspage_followup_reminder(incident.id)

        mock_slack.post_message.assert_not_called()

    def test_skips_when_followup_delay_not_configured(self):
        incident = self._make_incident(severity=IncidentSeverity.P0)
        self._make_link(incident, ExternalLinkType.SLACK)
        self._make_link(
            incident,
            ExternalLinkType.STATUSPAGE,
            url="https://manage.statuspage.io/incidents/abc123",
        )

        mock_slack = MagicMock()
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        with (
            patch(
                "firetower.incidents.tasks.statuspage.SlackService",
                return_value=mock_slack,
            ),
            patch.object(
                settings,
                "STATUSPAGE",
                {
                    "API_KEY": "test",
                    "PAGE_ID": "test",
                    "URL": "https://test.statuspage.io/",
                    "INITIAL_REMINDER_DELAY_MINUTES": 15,
                    "FOLLOWUP_REMINDER_DELAY_MINUTES": None,
                    "WARNING_BUFFER_MINUTES": 0,
                },
            ),
        ):
            send_statuspage_followup_reminder(incident.id)

        mock_slack.post_message.assert_not_called()

    def test_skips_when_incident_not_found(self):
        mock_slack = MagicMock()
        with patch(
            "firetower.incidents.tasks.statuspage.SlackService", return_value=mock_slack
        ):
            send_statuspage_followup_reminder(99999)

        mock_slack.post_message.assert_not_called()

    def test_skips_when_no_slack_link(self):
        incident = self._make_incident(severity=IncidentSeverity.P0)
        self._make_link(
            incident,
            ExternalLinkType.STATUSPAGE,
            url="https://manage.statuspage.io/incidents/abc123",
        )

        mock_slack = MagicMock()
        with patch(
            "firetower.incidents.tasks.statuspage.SlackService", return_value=mock_slack
        ):
            send_statuspage_followup_reminder(incident.id)

        mock_slack.post_message.assert_not_called()

    def test_posts_for_mitigated_status(self):
        incident = self._make_incident(
            severity=IncidentSeverity.P0, status=IncidentStatus.MITIGATED
        )
        self._make_link(incident, ExternalLinkType.SLACK)
        self._make_link(
            incident,
            ExternalLinkType.STATUSPAGE,
            url="https://manage.statuspage.io/incidents/abc123",
        )

        mock_slack = MagicMock()
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        with (
            patch(
                "firetower.incidents.tasks.statuspage.SlackService",
                return_value=mock_slack,
            ),
            patch(
                "firetower.incidents.tasks.statuspage.get_statuspage_followup_reminder_delay_minutes",
                return_value=self.CONFIGURED_FOLLOWUP_DELAY_MINUTES,
            ),
        ):
            send_statuspage_followup_reminder(incident.id)

        mock_slack.post_message.assert_called_once()

    def test_includes_ic_slack_mention(self):
        captain = User.objects.create_user(
            username="captain@example.com", email="captain@example.com"
        )
        ExternalProfile.objects.create(
            user=captain, type=ExternalProfileType.SLACK, external_id="U_CAPTAIN"
        )
        incident = self._make_incident(severity=IncidentSeverity.P0, captain=captain)
        self._make_link(incident, ExternalLinkType.SLACK)
        self._make_link(
            incident,
            ExternalLinkType.STATUSPAGE,
            url="https://manage.statuspage.io/incidents/abc123",
        )

        mock_slack = MagicMock()
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        with (
            patch(
                "firetower.incidents.tasks.statuspage.SlackService",
                return_value=mock_slack,
            ),
            patch(
                "firetower.incidents.tasks.statuspage.get_statuspage_followup_reminder_delay_minutes",
                return_value=self.CONFIGURED_FOLLOWUP_DELAY_MINUTES,
            ),
        ):
            send_statuspage_followup_reminder(incident.id)

        msg = mock_slack.post_message.call_args[0][1]
        assert "\n<@U_CAPTAIN>" in msg

    def test_omits_ic_without_slack_profile(self):
        captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Jane",
            last_name="Doe",
        )
        incident = self._make_incident(severity=IncidentSeverity.P0, captain=captain)
        self._make_link(incident, ExternalLinkType.SLACK)
        self._make_link(
            incident,
            ExternalLinkType.STATUSPAGE,
            url="https://manage.statuspage.io/incidents/abc123",
        )

        mock_slack = MagicMock()
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        with (
            patch(
                "firetower.incidents.tasks.statuspage.SlackService",
                return_value=mock_slack,
            ),
            patch(
                "firetower.incidents.tasks.statuspage.get_statuspage_followup_reminder_delay_minutes",
                return_value=self.CONFIGURED_FOLLOWUP_DELAY_MINUTES,
            ),
        ):
            send_statuspage_followup_reminder(incident.id)

        msg = mock_slack.post_message.call_args[0][1]
        assert "Jane Doe" not in msg


@pytest.mark.django_db
class TestSendActionItemReminder:
    CONFIGURED_HIGH_PRIORITY_COMMENT = "P0/P1 nag: this action item is overdue."
    CONFIGURED_MEDIUM_PRIORITY_COMMENT = "P2 nag: this action item is overdue."

    @pytest.fixture(autouse=True)
    def _configure_linear(self):
        linear_settings = {
            "CLIENT_ID": "test",
            "CLIENT_SECRET": "test",
            "API_KEY": "test",
            "TEAM_ID": "test",
            "PROJECT_ID": "test",
            "SYNC_IDENTIFIERS": False,
            "ACTION_ITEM_NAG_COMMENT_HIGH_PRIORITY": self.CONFIGURED_HIGH_PRIORITY_COMMENT,
            "ACTION_ITEM_NAG_COMMENT_MEDIUM_PRIORITY": self.CONFIGURED_MEDIUM_PRIORITY_COMMENT,
        }
        with patch.object(settings, "LINEAR", linear_settings):
            yield

    @pytest.fixture(autouse=True)
    def mock_sync(self):
        with patch(
            "firetower.incidents.tasks.action_items.sync_action_items_from_linear"
        ) as m:
            yield m

    @pytest.fixture
    def mock_linear(self):
        mock = MagicMock()
        mock.create_comment.return_value = True
        with patch(
            "firetower.incidents.tasks.action_items.LinearService",
            return_value=mock,
        ):
            yield mock

    def _make_incident(self, days_old: int = 45, **kwargs) -> Incident:
        defaults = {
            "title": "Test Incident",
            "status": IncidentStatus.DONE,
            "severity": IncidentSeverity.P0,
        }
        defaults.update(kwargs)
        incident = Incident.objects.create(**defaults)
        backdated = timezone.now() - timedelta(days=days_old)
        Incident.objects.filter(pk=incident.pk).update(created_at=backdated)
        incident.refresh_from_db()
        return incident

    def _make_action_item(self, incident: Incident, **kwargs) -> ActionItem:
        title = kwargs.pop("title", "Stale work")
        defaults = {
            "linear_issue_id": f"issue-{title}",
            "linear_identifier": f"ENG-{title}",
            "title": title,
            "status": ActionItemStatus.TODO,
            "priority": 1,
            "url": f"https://linear.app/team/issue/{title}",
        }
        defaults.update(kwargs)
        return ActionItem.objects.create(incident=incident, **defaults)

    def test_processes_incident_in_age_window(self, mock_sync):
        incident = self._make_incident(days_old=45)
        send_action_item_reminder()
        synced_ids = {c.args[0].id for c in mock_sync.call_args_list}
        assert synced_ids == {incident.id}

    def test_skips_incident_younger_than_global_floor(self, mock_sync):
        self._make_incident(days_old=5)
        send_action_item_reminder()
        mock_sync.assert_not_called()

    def test_skips_incident_older_than_max_age(self, mock_sync):
        self._make_incident(days_old=120)
        send_action_item_reminder()
        mock_sync.assert_not_called()

    def test_skips_low_severity_incident(self, mock_sync):
        self._make_incident(severity=IncidentSeverity.P2)
        send_action_item_reminder()
        mock_sync.assert_not_called()

    def test_skips_canceled_incident(self, mock_sync):
        self._make_incident(status=IncidentStatus.CANCELED)
        send_action_item_reminder()
        mock_sync.assert_not_called()

    def test_continues_when_sync_fails_for_one_incident(self, mock_sync, mock_linear):
        failing = self._make_incident(days_old=30)
        succeeding = self._make_incident(days_old=60)
        self._make_action_item(failing, title="should-not-nag")
        succeeding_item = self._make_action_item(succeeding, title="should-nag")

        def fake_sync(incident):
            if incident.id == failing.id:
                raise RuntimeError("linear is down")

        mock_sync.side_effect = fake_sync

        send_action_item_reminder()

        mock_linear.create_comment.assert_called_once_with(
            succeeding_item.linear_issue_id, self.CONFIGURED_HIGH_PRIORITY_COMMENT
        )

    def test_posts_high_priority_comment_for_p0(self, mock_linear):
        incident = self._make_incident()
        action_item = self._make_action_item(incident, priority=1)

        send_action_item_reminder()

        mock_linear.create_comment.assert_called_once_with(
            action_item.linear_issue_id, self.CONFIGURED_HIGH_PRIORITY_COMMENT
        )
        action_item.refresh_from_db()
        assert action_item.last_nag is not None

    def test_posts_high_priority_comment_for_p1(self, mock_linear):
        incident = self._make_incident()
        action_item = self._make_action_item(incident, priority=2)

        send_action_item_reminder()

        mock_linear.create_comment.assert_called_once_with(
            action_item.linear_issue_id, self.CONFIGURED_HIGH_PRIORITY_COMMENT
        )

    def test_posts_medium_priority_comment_for_p2(self, mock_linear):
        incident = self._make_incident(days_old=30)
        action_item = self._make_action_item(incident, priority=3)

        send_action_item_reminder()

        mock_linear.create_comment.assert_called_once_with(
            action_item.linear_issue_id, self.CONFIGURED_MEDIUM_PRIORITY_COMMENT
        )

    def test_nags_high_priority_at_seven_days(self, mock_linear):
        incident = self._make_incident(days_old=8)
        action_item = self._make_action_item(incident, priority=1)

        send_action_item_reminder()

        mock_linear.create_comment.assert_called_once_with(
            action_item.linear_issue_id, self.CONFIGURED_HIGH_PRIORITY_COMMENT
        )

    def test_skips_medium_priority_under_twenty_one_days(self, mock_linear):
        incident = self._make_incident(days_old=10)
        self._make_action_item(incident, priority=3)

        send_action_item_reminder()

        mock_linear.create_comment.assert_not_called()

    def test_runs_when_only_high_priority_comment_set(self, mock_linear):
        linear_only_high = {
            "ACTION_ITEM_NAG_COMMENT_HIGH_PRIORITY": self.CONFIGURED_HIGH_PRIORITY_COMMENT,
            "ACTION_ITEM_NAG_COMMENT_MEDIUM_PRIORITY": "",
        }
        incident = self._make_incident(days_old=30)
        urgent = self._make_action_item(incident, title="urgent", priority=1)
        self._make_action_item(incident, title="medium", priority=3)

        with patch.object(settings, "LINEAR", linear_only_high):
            send_action_item_reminder()

        mock_linear.create_comment.assert_called_once_with(
            urgent.linear_issue_id, self.CONFIGURED_HIGH_PRIORITY_COMMENT
        )

    def test_does_not_stamp_when_comment_returns_failure(self, mock_linear):
        incident = self._make_incident()
        action_item = self._make_action_item(incident)
        mock_linear.create_comment.return_value = False

        send_action_item_reminder()

        action_item.refresh_from_db()
        assert action_item.last_nag is None

    def test_does_not_stamp_when_create_comment_raises(self, mock_linear):
        incident = self._make_incident()
        action_item = self._make_action_item(incident)
        mock_linear.create_comment.side_effect = RuntimeError("linear is down")

        send_action_item_reminder()

        action_item.refresh_from_db()
        assert action_item.last_nag is None

    def test_skips_job_when_no_comment_configured(self, mock_sync):
        incident = self._make_incident()
        self._make_action_item(incident)

        with (
            patch.object(settings, "LINEAR", None),
            patch(
                "firetower.incidents.tasks.action_items.LinearService"
            ) as mock_service,
        ):
            send_action_item_reminder()

        mock_sync.assert_not_called()
        mock_service.assert_not_called()

    def test_skips_done_action_item(self, mock_linear):
        incident = self._make_incident()
        self._make_action_item(incident, status=ActionItemStatus.DONE)

        send_action_item_reminder()

        mock_linear.create_comment.assert_not_called()

    @pytest.mark.parametrize("priority", [0, 4])
    def test_skips_unranked_or_low_priority_action_item(self, mock_linear, priority):
        incident = self._make_incident()
        self._make_action_item(incident, priority=priority)

        send_action_item_reminder()

        mock_linear.create_comment.assert_not_called()

    def test_skips_recently_nagged_action_item(self, mock_linear):
        incident = self._make_incident()
        recent = timezone.now() - timedelta(days=2)
        self._make_action_item(incident, last_nag=recent)

        send_action_item_reminder()

        mock_linear.create_comment.assert_not_called()

    def test_processes_action_item_nagged_long_ago(self, mock_linear):
        incident = self._make_incident()
        stale = timezone.now() - timedelta(days=14)
        action_item = self._make_action_item(incident, last_nag=stale)

        send_action_item_reminder()

        mock_linear.create_comment.assert_called_once_with(
            action_item.linear_issue_id, self.CONFIGURED_HIGH_PRIORITY_COMMENT
        )

    def test_renders_template_variables(self, mock_linear):
        template = (
            "SLO={{ slo_days }} age={{ incident_age_days }} "
            "past={{ days_past_due }} left={{ days_left }} "
            "passed={{ slo_passed }} id={{ action_item.linear_identifier }} "
            "title={{ incident.title }}"
        )
        with patch.dict(
            settings.LINEAR, {"ACTION_ITEM_NAG_COMMENT_HIGH_PRIORITY": template}
        ):
            incident = self._make_incident(days_old=10, title="Some outage")
            action_item = self._make_action_item(incident, priority=1)

            send_action_item_reminder()

        expected = (
            f"SLO=14 age=10 past=0 left=4 passed=False "
            f"id={action_item.linear_identifier} title=Some outage"
        )
        mock_linear.create_comment.assert_called_once_with(
            action_item.linear_issue_id, expected
        )

    def test_renders_medium_tier_variables(self, mock_linear):
        template = "SLO={{ slo_days }} past={{ days_past_due }}"
        with patch.dict(
            settings.LINEAR, {"ACTION_ITEM_NAG_COMMENT_MEDIUM_PRIORITY": template}
        ):
            incident = self._make_incident(days_old=35)
            action_item = self._make_action_item(incident, priority=3)

            send_action_item_reminder()

        mock_linear.create_comment.assert_called_once_with(
            action_item.linear_issue_id, "SLO=30 past=5"
        )

    def test_skips_when_template_has_syntax_error(self, mock_linear):
        with patch.dict(
            settings.LINEAR,
            {"ACTION_ITEM_NAG_COMMENT_HIGH_PRIORITY": "{{ unterminated "},
        ):
            incident = self._make_incident()
            action_item = self._make_action_item(incident, priority=1)

            send_action_item_reminder()

        mock_linear.create_comment.assert_not_called()
        action_item.refresh_from_db()
        assert action_item.last_nag is None
