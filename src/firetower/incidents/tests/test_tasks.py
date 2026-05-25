from unittest.mock import MagicMock, call, patch

import pytest
from django_q.models import Schedule

from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from firetower.incidents.tasks import (
    ARCHIVE_NOTICE,
    archive_stale_channels,
    datadog_log,
    schedule_demo,
)


class TestDatadogLogTaskName:
    @patch("firetower.incidents.tasks.statsd")
    def test_replaces_invalid_chars_with_underscore(self, mock_statsd):
        def f_with_bad_chars() -> None:
            pass

        f_with_bad_chars.__name__ = "task with spaces & symbols!"
        wrapped = datadog_log(f_with_bad_chars)
        wrapped()

        expected_tags = ["task:task_with_spaces___symbols_"]
        mock_statsd.increment.assert_any_call("django_q.task.run", 1, expected_tags)

    @patch("firetower.incidents.tasks.statsd")
    def test_preserves_alphanumerics_dash_underscore_dot_slash(self, mock_statsd):
        def f() -> None:
            pass

        f.__name__ = "namespace/sub-task_v1.2"
        wrapped = datadog_log(f)
        wrapped()

        expected_tags = ["task:namespace/sub-task_v1.2"]
        mock_statsd.increment.assert_any_call("django_q.task.run", 1, expected_tags)

    @patch("firetower.incidents.tasks.statsd")
    def test_replaces_consecutive_invalid_chars_individually(self, mock_statsd):
        def f() -> None:
            pass

        f.__name__ = "a@@b"
        wrapped = datadog_log(f)
        wrapped()

        expected_tags = ["task:a__b"]
        mock_statsd.increment.assert_any_call("django_q.task.run", 1, expected_tags)


class TestDatadogLogStatsdIncrements:
    @patch("firetower.incidents.tasks.statsd")
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

    @patch("firetower.incidents.tasks.statsd")
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

    @patch("firetower.incidents.tasks.statsd")
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

    @patch("firetower.incidents.tasks.statsd")
    def test_re_raises_exception_from_wrapped_function(self, mock_statsd):
        def f() -> None:
            raise ValueError("should propagate")

        f.__name__ = "raises"
        wrapped = datadog_log(f)

        with pytest.raises(ValueError, match="should propagate"):
            wrapped()


class TestScheduleDemoPrivateIncident:
    @patch("firetower.incidents.tasks.statsd")
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

    @patch("firetower.incidents.tasks.statsd")
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
class TestArchiveStaleChannels:
    @pytest.fixture(autouse=True)
    def _no_sleep(self):
        with patch("firetower.incidents.tasks.time.sleep"):
            yield

    def _make_incident(self, **kwargs):
        defaults = {
            "title": "Test Incident",
            "status": IncidentStatus.DONE,
            "severity": IncidentSeverity.P2,
        }
        defaults.update(kwargs)
        return Incident.objects.create(**defaults)

    def _make_link(self, incident, channel_id="C12345"):
        return ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url=f"https://sentry.slack.com/archives/{channel_id}",
        )

    OWN_BOT_ID = "B_FIRETOWER"

    def test_archives_channel_with_no_history(self):
        incident = self._make_incident()
        self._make_link(incident, "C_EMPTY")

        mock_slack = MagicMock()
        mock_slack.client = True
        mock_slack.bot_id = self.OWN_BOT_ID
        mock_slack.parse_channel_id_from_url.return_value = "C_EMPTY"
        mock_slack.get_channel_info.return_value = {
            "id": "C_EMPTY",
            "name": "inc-2000",
            "is_private": False,
            "is_archived": False,
        }
        mock_slack.get_channel_history.return_value = []
        mock_slack.archive_channel.return_value = True

        with patch("firetower.incidents.tasks.SlackService", return_value=mock_slack):
            archive_stale_channels.__wrapped__()

        mock_slack.get_channel_history.assert_called_once_with("C_EMPTY")
        mock_slack.post_message.assert_called_once_with("C_EMPTY", ARCHIVE_NOTICE)
        mock_slack.archive_channel.assert_called_once_with("C_EMPTY")

    def test_skips_channel_with_human_messages(self):
        incident = self._make_incident()
        self._make_link(incident, "C_ACTIVE")

        mock_slack = MagicMock()
        mock_slack.client = True
        mock_slack.bot_id = self.OWN_BOT_ID
        mock_slack.parse_channel_id_from_url.return_value = "C_ACTIVE"
        mock_slack.get_channel_info.return_value = {
            "id": "C_ACTIVE",
            "name": "inc-2001",
            "is_private": False,
            "is_archived": False,
        }
        mock_slack.get_channel_history.return_value = [
            {"type": "message", "user": "U123", "text": "still here", "ts": "1.0"}
        ]

        with patch("firetower.incidents.tasks.SlackService", return_value=mock_slack):
            archive_stale_channels.__wrapped__()

        mock_slack.post_message.assert_not_called()
        mock_slack.archive_channel.assert_not_called()

    def test_archives_channel_with_only_own_bot_messages(self):
        incident = self._make_incident()
        self._make_link(incident, "C_BOTONLY")

        mock_slack = MagicMock()
        mock_slack.client = True
        mock_slack.bot_id = self.OWN_BOT_ID
        mock_slack.parse_channel_id_from_url.return_value = "C_BOTONLY"
        mock_slack.get_channel_info.return_value = {
            "id": "C_BOTONLY",
            "name": "inc-2001",
            "is_private": False,
            "is_archived": False,
        }
        mock_slack.get_channel_history.return_value = [
            {
                "type": "message",
                "bot_id": self.OWN_BOT_ID,
                "text": ARCHIVE_NOTICE,
                "ts": "1.0",
            }
        ]
        mock_slack.post_message.return_value = "2.0"
        mock_slack.archive_channel.return_value = True

        with patch("firetower.incidents.tasks.SlackService", return_value=mock_slack):
            archive_stale_channels.__wrapped__()

        mock_slack.archive_channel.assert_called_once_with("C_BOTONLY")

    def test_skips_channel_with_other_bot_messages(self):
        incident = self._make_incident()
        self._make_link(incident, "C_OTHERBOT")

        mock_slack = MagicMock()
        mock_slack.client = True
        mock_slack.bot_id = self.OWN_BOT_ID
        mock_slack.parse_channel_id_from_url.return_value = "C_OTHERBOT"
        mock_slack.get_channel_info.return_value = {
            "id": "C_OTHERBOT",
            "name": "inc-2001",
            "is_private": False,
            "is_archived": False,
        }
        mock_slack.get_channel_history.return_value = [
            {
                "type": "message",
                "bot_id": "B_SOMEONE_ELSE",
                "text": "alert from another bot",
                "ts": "1.0",
            }
        ]

        with patch("firetower.incidents.tasks.SlackService", return_value=mock_slack):
            archive_stale_channels.__wrapped__()

        mock_slack.post_message.assert_not_called()
        mock_slack.archive_channel.assert_not_called()

    def test_skips_already_archived_channel(self):
        incident = self._make_incident()
        self._make_link(incident, "C_ARCHIVED")

        mock_slack = MagicMock()
        mock_slack.client = True
        mock_slack.parse_channel_id_from_url.return_value = "C_ARCHIVED"
        mock_slack.get_channel_info.return_value = {
            "id": "C_ARCHIVED",
            "name": "inc-2002",
            "is_private": False,
            "is_archived": True,
        }

        with patch("firetower.incidents.tasks.SlackService", return_value=mock_slack):
            archive_stale_channels.__wrapped__()

        mock_slack.get_channel_history.assert_not_called()
        mock_slack.archive_channel.assert_not_called()

    def test_skips_channel_on_api_error(self):
        incident = self._make_incident()
        self._make_link(incident, "C_ERROR")

        mock_slack = MagicMock()
        mock_slack.client = True
        mock_slack.parse_channel_id_from_url.return_value = "C_ERROR"
        mock_slack.get_channel_info.return_value = None

        with patch("firetower.incidents.tasks.SlackService", return_value=mock_slack):
            archive_stale_channels.__wrapped__()

        mock_slack.get_channel_history.assert_not_called()
        mock_slack.archive_channel.assert_not_called()

    def test_disables_schedule_when_no_client(self):
        schedule = Schedule.objects.get(name="archive_stale_channels")
        assert schedule.repeats == -1

        mock_slack = MagicMock()
        mock_slack.client = None

        with patch("firetower.incidents.tasks.SlackService", return_value=mock_slack):
            archive_stale_channels.__wrapped__()

        schedule.refresh_from_db()
        assert schedule.repeats == 0

    def test_continues_on_single_channel_exception(self):
        inc1 = self._make_incident()
        inc2 = self._make_incident()
        self._make_link(inc1, "C_BAD")
        self._make_link(inc2, "C_GOOD")

        mock_slack = MagicMock()
        mock_slack.client = True
        mock_slack.bot_id = self.OWN_BOT_ID
        mock_slack.parse_channel_id_from_url.side_effect = (
            lambda url: "C_BAD" if "C_BAD" in url else "C_GOOD"
        )
        mock_slack.get_channel_info.side_effect = lambda cid: (
            (_ for _ in ()).throw(Exception("boom"))
            if cid == "C_BAD"
            else {
                "id": "C_GOOD",
                "name": "inc-x",
                "is_private": False,
                "is_archived": False,
            }
        )
        mock_slack.get_channel_history.return_value = []
        mock_slack.archive_channel.return_value = True

        with patch("firetower.incidents.tasks.SlackService", return_value=mock_slack):
            archive_stale_channels.__wrapped__()

        mock_slack.archive_channel.assert_called_once_with("C_GOOD")

    def test_deletes_notice_on_failed_archive(self):
        incident = self._make_incident()
        self._make_link(incident, "C_FAIL")

        mock_slack = MagicMock()
        mock_slack.client = True
        mock_slack.bot_id = self.OWN_BOT_ID
        mock_slack.parse_channel_id_from_url.return_value = "C_FAIL"
        mock_slack.get_channel_info.return_value = {
            "id": "C_FAIL",
            "name": "inc-2010",
            "is_private": False,
            "is_archived": False,
        }
        mock_slack.get_channel_history.return_value = []
        mock_slack.post_message.return_value = "1234.5678"
        mock_slack.archive_channel.return_value = False

        with patch("firetower.incidents.tasks.SlackService", return_value=mock_slack):
            archive_stale_channels.__wrapped__()

        mock_slack.post_message.assert_called_once_with("C_FAIL", ARCHIVE_NOTICE)
        mock_slack.delete_message.assert_called_once_with("C_FAIL", "1234.5678")

    def test_skips_channel_on_history_api_error(self):
        incident = self._make_incident()
        self._make_link(incident, "C_BROKEN")

        mock_slack = MagicMock()
        mock_slack.client = True
        mock_slack.bot_id = self.OWN_BOT_ID
        mock_slack.parse_channel_id_from_url.return_value = "C_BROKEN"
        mock_slack.get_channel_info.return_value = {
            "id": "C_BROKEN",
            "name": "inc-2011",
            "is_private": False,
            "is_archived": False,
        }
        mock_slack.get_channel_history.side_effect = Exception("API error")

        with patch("firetower.incidents.tasks.SlackService", return_value=mock_slack):
            archive_stale_channels.__wrapped__()

        mock_slack.post_message.assert_not_called()
        mock_slack.archive_channel.assert_not_called()

    def test_deletes_notice_on_archive_exception(self):
        incident = self._make_incident()
        self._make_link(incident, "C_THROW")

        mock_slack = MagicMock()
        mock_slack.client = True
        mock_slack.bot_id = self.OWN_BOT_ID
        mock_slack.parse_channel_id_from_url.return_value = "C_THROW"
        mock_slack.get_channel_info.return_value = {
            "id": "C_THROW",
            "name": "inc-2013",
            "is_private": False,
            "is_archived": False,
        }
        mock_slack.get_channel_history.return_value = []
        mock_slack.post_message.return_value = "99.99"
        mock_slack.archive_channel.side_effect = ConnectionError("network timeout")

        with patch("firetower.incidents.tasks.SlackService", return_value=mock_slack):
            archive_stale_channels.__wrapped__()

        mock_slack.delete_message.assert_called_once_with("C_THROW", "99.99")

    def test_skips_archive_when_post_message_fails(self):
        incident = self._make_incident()
        self._make_link(incident, "C_NOPOST")

        mock_slack = MagicMock()
        mock_slack.client = True
        mock_slack.bot_id = self.OWN_BOT_ID
        mock_slack.parse_channel_id_from_url.return_value = "C_NOPOST"
        mock_slack.get_channel_info.return_value = {
            "id": "C_NOPOST",
            "name": "inc-2012",
            "is_private": False,
            "is_archived": False,
        }
        mock_slack.get_channel_history.return_value = []
        mock_slack.post_message.return_value = None

        with patch("firetower.incidents.tasks.SlackService", return_value=mock_slack):
            archive_stale_channels.__wrapped__()

        mock_slack.archive_channel.assert_not_called()

    def test_skips_active_incident_channels(self):
        active = self._make_incident(status=IncidentStatus.ACTIVE)
        self._make_link(active, "C_ACTIVE_INC")
        mitigated = self._make_incident(status=IncidentStatus.MITIGATED)
        self._make_link(mitigated, "C_MITIGATED_INC")
        postmortem = self._make_incident(status=IncidentStatus.POSTMORTEM)
        self._make_link(postmortem, "C_POSTMORTEM_INC")

        mock_slack = MagicMock()
        mock_slack.client = True
        mock_slack.bot_id = self.OWN_BOT_ID

        with patch("firetower.incidents.tasks.SlackService", return_value=mock_slack):
            archive_stale_channels.__wrapped__()

        mock_slack.parse_channel_id_from_url.assert_not_called()
        mock_slack.archive_channel.assert_not_called()

    def test_includes_cancelled_incident_channels(self):
        incident = self._make_incident(status=IncidentStatus.CANCELLED)
        self._make_link(incident, "C_CANCELLED")

        mock_slack = MagicMock()
        mock_slack.client = True
        mock_slack.bot_id = self.OWN_BOT_ID
        mock_slack.parse_channel_id_from_url.return_value = "C_CANCELLED"
        mock_slack.get_channel_info.return_value = {
            "id": "C_CANCELLED",
            "name": "inc-3000",
            "is_private": False,
            "is_archived": False,
        }
        mock_slack.get_channel_history.return_value = []
        mock_slack.get_thread_replies.return_value = []
        mock_slack.archive_channel.return_value = True

        with patch("firetower.incidents.tasks.SlackService", return_value=mock_slack):
            archive_stale_channels.__wrapped__()

        mock_slack.archive_channel.assert_called_once_with("C_CANCELLED")

    def test_fetches_full_history_not_limited(self):
        incident = self._make_incident()
        self._make_link(incident, "C_DEEPHISTORY")

        mock_slack = MagicMock()
        mock_slack.client = True
        mock_slack.bot_id = self.OWN_BOT_ID
        mock_slack.parse_channel_id_from_url.return_value = "C_DEEPHISTORY"
        mock_slack.get_channel_info.return_value = {
            "id": "C_DEEPHISTORY",
            "name": "inc-4000",
            "is_private": False,
            "is_archived": False,
        }
        mock_slack.get_channel_history.return_value = [
            {"type": "message", "bot_id": self.OWN_BOT_ID, "text": "bot1", "ts": "5.0"},
            {"type": "message", "bot_id": self.OWN_BOT_ID, "text": "bot2", "ts": "4.0"},
            {"type": "message", "bot_id": self.OWN_BOT_ID, "text": "bot3", "ts": "3.0"},
            {"type": "message", "bot_id": self.OWN_BOT_ID, "text": "bot4", "ts": "2.0"},
            {"type": "message", "bot_id": self.OWN_BOT_ID, "text": "bot5", "ts": "1.5"},
            {
                "type": "message",
                "user": "U_HUMAN",
                "text": "old human msg",
                "ts": "1.0",
            },
        ]

        with patch("firetower.incidents.tasks.SlackService", return_value=mock_slack):
            archive_stale_channels.__wrapped__()

        mock_slack.get_channel_history.assert_called_once_with("C_DEEPHISTORY")
        mock_slack.archive_channel.assert_not_called()

    def test_skips_channel_with_human_thread_replies(self):
        incident = self._make_incident()
        self._make_link(incident, "C_THREADS")

        mock_slack = MagicMock()
        mock_slack.client = True
        mock_slack.bot_id = self.OWN_BOT_ID
        mock_slack.parse_channel_id_from_url.return_value = "C_THREADS"
        mock_slack.get_channel_info.return_value = {
            "id": "C_THREADS",
            "name": "inc-5000",
            "is_private": False,
            "is_archived": False,
        }
        mock_slack.get_channel_history.return_value = [
            {
                "type": "message",
                "bot_id": self.OWN_BOT_ID,
                "text": "bot msg with thread",
                "ts": "1.0",
                "reply_count": 2,
            }
        ]
        mock_slack.get_thread_replies.return_value = [
            {"type": "message", "user": "U_HUMAN", "text": "reply", "ts": "1.1"}
        ]

        with patch("firetower.incidents.tasks.SlackService", return_value=mock_slack):
            archive_stale_channels.__wrapped__()

        mock_slack.get_thread_replies.assert_called_once_with("C_THREADS", "1.0")
        mock_slack.archive_channel.assert_not_called()

    def test_archives_channel_with_bot_only_threads(self):
        incident = self._make_incident()
        self._make_link(incident, "C_BOTTHREADS")

        mock_slack = MagicMock()
        mock_slack.client = True
        mock_slack.bot_id = self.OWN_BOT_ID
        mock_slack.parse_channel_id_from_url.return_value = "C_BOTTHREADS"
        mock_slack.get_channel_info.return_value = {
            "id": "C_BOTTHREADS",
            "name": "inc-5001",
            "is_private": False,
            "is_archived": False,
        }
        mock_slack.get_channel_history.return_value = [
            {
                "type": "message",
                "bot_id": self.OWN_BOT_ID,
                "text": "bot msg",
                "ts": "1.0",
                "reply_count": 1,
            }
        ]
        mock_slack.get_thread_replies.return_value = []
        mock_slack.post_message.return_value = "2.0"
        mock_slack.archive_channel.return_value = True

        with patch("firetower.incidents.tasks.SlackService", return_value=mock_slack):
            archive_stale_channels.__wrapped__()

        mock_slack.archive_channel.assert_called_once_with("C_BOTTHREADS")
