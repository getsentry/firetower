from unittest.mock import MagicMock, call, patch

import pytest

from firetower.incidents.tasks import datadog_log, schedule_demo


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
