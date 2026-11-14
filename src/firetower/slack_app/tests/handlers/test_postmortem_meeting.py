from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from django.conf import settings

from firetower.incidents.models import ExternalLinkType, IncidentStatus
from firetower.slack_app.handlers.postmortem_meeting import (
    handle_postmortem_meeting_message,
    is_postmortem_meeting_message,
    parse_meeting_start,
)

from .conftest import CHANNEL_ID

SCHEDULER_BOT_ID = "U_SCHEDULER"
MEET_URL = "https://meet.google.com/abc-defg-hij"


@pytest.fixture(autouse=True)
def _configure_scheduler_bot():
    slack_settings = {
        **settings.SLACK,
        "POSTMORTEM_SCHEDULER_BOT_USER_ID": SCHEDULER_BOT_ID,
    }
    with patch.object(settings, "SLACK", slack_settings):
        yield


def _event(user=SCHEDULER_BOT_ID, text=f"Scheduled: <{MEET_URL}|Join>"):
    return {"type": "message", "channel": CHANNEL_ID, "user": user, "text": text}


class TestIsPostmortemMeetingMessage:
    def test_matches_scheduler_bot_message_with_meet_link(self):
        assert is_postmortem_meeting_message(_event())

    def test_ignores_other_users(self):
        assert not is_postmortem_meeting_message(_event(user="U_OTHER"))

    def test_ignores_messages_without_meet_link(self):
        assert not is_postmortem_meeting_message(_event(text="Scheduled!"))

    def test_ignores_when_no_scheduler_bot_configured(self):
        settings.SLACK["POSTMORTEM_SCHEDULER_BOT_USER_ID"] = ""
        settings.SLACK["TRIAGE_BOT_USER_ID"] = ""
        assert not is_postmortem_meeting_message(_event(user=""))


@pytest.mark.django_db
class TestHandlePostmortemMeetingMessage:
    def test_records_meeting_for_postmortem_incident(self, incident):
        incident.status = IncidentStatus.POSTMORTEM
        incident.save()

        handle_postmortem_meeting_message(_event())

        assert (
            incident.external_links.get(
                type=ExternalLinkType.POSTMORTEM_MEETING_LINK
            ).url
            == MEET_URL
        )

    def test_ignores_active_incident(self, incident):
        handle_postmortem_meeting_message(_event())

        assert not incident.external_links.filter(
            type=ExternalLinkType.POSTMORTEM_MEETING_LINK
        ).exists()

    @patch(
        "firetower.slack_app.handlers.postmortem_meeting.schedule_postmortem_final_call"
    )
    def test_schedules_final_call_from_threaded_reply(self, mock_schedule, incident):
        incident.status = IncidentStatus.POSTMORTEM
        incident.save()
        event = {
            **_event(text=f"Scheduled for 2026-11-03T17:00:00Z: <{MEET_URL}|Join>"),
            "thread_ts": "1111.2222",
        }

        handle_postmortem_meeting_message(event)

        mock_schedule.assert_called_once_with(
            incident,
            CHANNEL_ID,
            "1111.2222",
            datetime(2026, 11, 3, 17, 0, tzinfo=UTC),
        )

    @patch(
        "firetower.slack_app.handlers.postmortem_meeting.schedule_postmortem_final_call"
    )
    def test_skips_final_call_without_start_time(self, mock_schedule, incident):
        incident.status = IncidentStatus.POSTMORTEM
        incident.save()

        handle_postmortem_meeting_message({**_event(), "thread_ts": "1111.2222"})

        mock_schedule.assert_not_called()

    @patch(
        "firetower.slack_app.handlers.postmortem_meeting.schedule_postmortem_final_call"
    )
    def test_skips_final_call_outside_thread(self, mock_schedule, incident):
        incident.status = IncidentStatus.POSTMORTEM
        incident.save()

        handle_postmortem_meeting_message(
            _event(text=f"2026-11-03T17:00:00Z <{MEET_URL}|Join>")
        )

        mock_schedule.assert_not_called()


class TestParseMeetingStart:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("at 2026-11-03T17:00:00Z", datetime(2026, 11, 3, 17, 0, tzinfo=UTC)),
            ("at 2026-11-03T17:00Z", datetime(2026, 11, 3, 17, 0, tzinfo=UTC)),
            (
                "at 2026-11-03T09:00:00-08:00",
                datetime(2026, 11, 3, 17, 0, tzinfo=UTC),
            ),
            ("at 2026-11-03T17:00:00", None),
            ("next Tuesday", None),
        ],
    )
    def test_parse(self, text, expected):
        assert parse_meeting_start(text) == expected
