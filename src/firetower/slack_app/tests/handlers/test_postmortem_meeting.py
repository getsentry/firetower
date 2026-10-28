from unittest.mock import patch

import pytest
from django.conf import settings

from firetower.incidents.models import ExternalLinkType, IncidentStatus
from firetower.slack_app.handlers.postmortem_meeting import (
    handle_postmortem_meeting_message,
    is_postmortem_meeting_message,
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
            incident.external_links.get(type=ExternalLinkType.POSTMORTEM_MEETING).url
            == MEET_URL
        )

    def test_ignores_active_incident(self, incident):
        handle_postmortem_meeting_message(_event())

        assert not incident.external_links.filter(
            type=ExternalLinkType.POSTMORTEM_MEETING
        ).exists()
