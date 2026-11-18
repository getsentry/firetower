from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.contrib.auth.models import User

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    TimelineEvent,
    TimelineEventSource,
    TimelineEventType,
)
from firetower.incidents.tasks import send_stale_incident_nudges
from firetower.incidents.tasks.stale_incidents import (
    count_business_days,
    subtract_business_days,
)
from firetower.integrations.services.slack import SlackReadError

# Wednesday
NOW = datetime(2026, 11, 18, 14, 0, tzinfo=UTC)
CHANNEL_ID = "C12345"


def _ts(moment: datetime) -> str:
    return f"{moment.timestamp():.6f}"


class TestBusinessDays:
    def test_subtract_skips_weekend(self):
        monday = datetime(2026, 11, 16, 14, 0, tzinfo=UTC)
        assert subtract_business_days(monday, 1) == datetime(
            2026, 11, 13, 14, 0, tzinfo=UTC
        )
        assert subtract_business_days(monday, 2) == datetime(
            2026, 11, 12, 14, 0, tzinfo=UTC
        )

    def test_count_skips_weekend(self):
        thursday = datetime(2026, 11, 12, 14, 0, tzinfo=UTC)
        assert count_business_days(thursday, NOW) == 4


@pytest.mark.django_db
class TestSendStaleIncidentNudges:
    @pytest.fixture(autouse=True)
    def _enable_nudges(self):
        with patch.dict(settings.SLACK, {"STALE_INCIDENT_NUDGES_ENABLED": True}):
            yield

    @pytest.fixture
    def slack(self):
        mock_slack = MagicMock()
        mock_slack.parse_channel_id_from_url.return_value = CHANNEL_ID
        mock_slack.get_channel_history.return_value = [
            {
                "type": "message",
                "user": "UFIRETOWER",
                "bot_id": "BFIRETOWER",
                "ts": _ts(NOW - timedelta(days=7)),
            }
        ]
        mock_slack.get_thread_replies.return_value = []
        mock_slack.post_message.return_value = "1234.5678"
        with patch(
            "firetower.incidents.tasks.stale_incidents.SlackService",
            return_value=mock_slack,
        ):
            yield mock_slack

    def _run(self, now: datetime = NOW) -> None:
        with patch("firetower.incidents.tasks.stale_incidents.timezone") as mock_tz:
            mock_tz.now.return_value = now
            send_stale_incident_nudges()

    def _make_captain(self, tz: str = "America/Los_Angeles") -> User:
        captain = User.objects.create_user(username="captain@example.com")
        ExternalProfile.objects.create(
            user=captain, type=ExternalProfileType.SLACK, external_id="UCAPTAIN"
        )
        captain.userprofile.timezone = tz
        captain.userprofile.save()
        return captain

    def _make_incident(
        self,
        status: str = IncidentStatus.ACTIVE,
        created_at: datetime = NOW - timedelta(days=7),
        status_changed_at: datetime | None = None,
        **kwargs,
    ) -> Incident:
        incident = Incident.objects.create(
            title="Test Incident",
            status=status,
            severity=IncidentSeverity.P3,
            **kwargs,
        )
        Incident.objects.filter(pk=incident.pk).update(created_at=created_at)
        incident.refresh_from_db()
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url=f"https://sentry.slack.com/archives/{CHANNEL_ID}",
        )
        if status_changed_at:
            TimelineEvent.objects.create(
                incident=incident,
                source=TimelineEventSource.USER,
                event_type=TimelineEventType.STATUS_CHANGED,
                occurred_at=status_changed_at,
                payload={"old": "Active", "new": status},
            )
        return incident

    def test_nudges_captain_of_quiet_stale_incident(self, slack):
        captain = self._make_captain()
        incident = self._make_incident(
            status=IncidentStatus.MITIGATED,
            status_changed_at=datetime(2026, 11, 11, 15, 0, tzinfo=UTC),
            captain=captain,
        )
        slack.get_channel_history.return_value = [
            {
                "type": "message",
                "user": "UHUMAN",
                "ts": _ts(datetime(2026, 11, 12, 10, 0, tzinfo=UTC)),
            },
            {
                "type": "message",
                "user": "UBOT",
                "bot_id": "BBOT",
                "ts": _ts(NOW - timedelta(hours=1)),
            },
            {
                "type": "message",
                "subtype": "channel_join",
                "user": "UJOINER",
                "ts": _ts(NOW - timedelta(hours=2)),
            },
        ]

        self._run()

        slack.post_message.assert_called_once()
        channel_id, message = slack.post_message.call_args.args
        assert channel_id == CHANNEL_ID
        assert message.startswith("<@UCAPTAIN> ")
        assert "*Mitigated* since Wed Nov 11" in message
        assert "for 4 business days" in message
        assert "`/inc resolved`" in message
        assert "`/inc mitigated`" not in message
        incident.refresh_from_db()
        assert incident.last_nudge_at == NOW

    def test_active_incident_suggests_mitigated_or_resolved(self, slack):
        self._make_incident()

        self._run()

        message = slack.post_message.call_args.args[1]
        assert "`/inc mitigated` or `/inc resolved`" in message
        assert not message.startswith("<@")

    def test_skips_when_human_posted_recently(self, slack):
        self._make_incident()
        slack.get_channel_history.return_value = [
            {"type": "message", "user": "UHUMAN", "ts": _ts(NOW - timedelta(hours=12))}
        ]

        self._run()

        slack.post_message.assert_not_called()

    def test_skips_when_human_replied_in_thread_recently(self, slack):
        self._make_incident()
        parent_ts = _ts(NOW - timedelta(days=6))
        slack.get_channel_history.return_value = [
            {
                "type": "message",
                "user": "UBOT",
                "bot_id": "BBOT",
                "ts": parent_ts,
                "latest_reply": _ts(NOW - timedelta(hours=3)),
            }
        ]
        slack.get_thread_replies.return_value = [
            {"type": "message", "user": "UHUMAN", "ts": _ts(NOW - timedelta(hours=3))}
        ]

        self._run()

        slack.get_thread_replies.assert_called_once_with(
            CHANNEL_ID, parent_ts, raise_on_error=True
        )
        slack.post_message.assert_not_called()

    def test_thread_with_only_bot_replies_counts_as_quiet(self, slack):
        self._make_incident()
        slack.get_channel_history.return_value = [
            {
                "type": "message",
                "user": "UBOT",
                "bot_id": "BBOT",
                "ts": _ts(NOW - timedelta(days=6)),
                "latest_reply": _ts(NOW - timedelta(hours=3)),
            }
        ]

        self._run()

        slack.post_message.assert_called_once()

    def test_skips_when_thread_read_fails(self, slack):
        self._make_incident()
        slack.get_channel_history.return_value = [
            {
                "type": "message",
                "user": "UBOT",
                "bot_id": "BBOT",
                "ts": _ts(NOW - timedelta(days=6)),
                "latest_reply": _ts(NOW - timedelta(hours=3)),
            }
        ]
        slack.get_thread_replies.side_effect = SlackReadError("boom")

        self._run()

        slack.post_message.assert_not_called()

    def test_shows_status_date_in_captain_timezone(self, slack):
        self._make_incident(
            status=IncidentStatus.MITIGATED,
            status_changed_at=datetime(2026, 11, 13, 1, 0, tzinfo=UTC),
            captain=self._make_captain("America/Los_Angeles"),
        )

        self._run()

        assert "since Thu Nov 12" in slack.post_message.call_args.args[1]

    def test_skips_recent_status_change(self, slack):
        self._make_incident(status_changed_at=NOW - timedelta(hours=12))

        self._run()

        slack.post_message.assert_not_called()

    def test_skips_new_incident(self, slack):
        self._make_incident(created_at=NOW - timedelta(hours=12))

        self._run()

        slack.post_message.assert_not_called()

    def test_waits_three_business_days_between_nudges(self, slack):
        incident = self._make_incident(created_at=NOW - timedelta(days=14))
        Incident.objects.filter(pk=incident.pk).update(
            last_nudge_at=NOW - timedelta(days=2)
        )

        self._run()
        slack.post_message.assert_not_called()

        self._run(now=NOW + timedelta(days=1))
        slack.post_message.assert_called_once()

    @pytest.mark.parametrize("status", [IncidentStatus.POSTMORTEM, IncidentStatus.DONE])
    def test_skips_closed_and_postmortem_incidents(self, slack, status):
        self._make_incident(status=status)

        self._run()

        slack.post_message.assert_not_called()

    def test_skips_private_incident(self, slack):
        self._make_incident(is_private=True)

        self._run()

        slack.post_message.assert_not_called()

    def test_says_one_business_day_in_singular(self, slack):
        self._make_incident()
        slack.get_channel_history.return_value = [
            {
                "type": "message",
                "user": "UHUMAN",
                "ts": _ts(NOW - timedelta(days=1, hours=1)),
            }
        ]

        self._run()

        assert "for 1 business day." in slack.post_message.call_args.args[1]

    @pytest.mark.parametrize(
        ("tz", "now", "nudged"),
        [
            ("America/Los_Angeles", datetime(2026, 11, 21, 7, 59, tzinfo=UTC), True),
            ("America/Los_Angeles", datetime(2026, 11, 21, 8, 0, tzinfo=UTC), False),
            ("America/Los_Angeles", datetime(2026, 11, 23, 7, 59, tzinfo=UTC), False),
            ("America/Los_Angeles", datetime(2026, 11, 23, 8, 0, tzinfo=UTC), True),
            ("Europe/Vienna", datetime(2026, 11, 20, 22, 59, tzinfo=UTC), True),
            ("Europe/Vienna", datetime(2026, 11, 20, 23, 0, tzinfo=UTC), False),
            ("Europe/Vienna", datetime(2026, 11, 22, 23, 0, tzinfo=UTC), True),
        ],
    )
    def test_only_nudges_on_captain_weekdays(self, slack, tz, now, nudged):
        self._make_incident(captain=self._make_captain(tz))

        self._run(now=now)

        assert slack.post_message.called is nudged

    def test_fetches_and_stores_missing_captain_timezone(self, slack):
        captain = self._make_captain(tz="")
        self._make_incident(captain=captain)
        slack.get_user_info.return_value = {"timezone": "America/New_York"}

        self._run()

        slack.get_user_info.assert_called_once_with("UCAPTAIN")
        captain.userprofile.refresh_from_db()
        assert captain.userprofile.timezone == "America/New_York"
        slack.post_message.assert_called_once()

    @pytest.mark.parametrize(
        "user_info", [None, {"timezone": ""}, {"timezone": "Not/AZone"}]
    )
    def test_uses_utc_when_captain_timezone_is_unknown(self, slack, user_info):
        captain = self._make_captain(tz="")
        if user_info and user_info["timezone"]:
            captain.userprofile.timezone = user_info["timezone"]
            captain.userprofile.save()
        self._make_incident(captain=captain)
        slack.get_user_info.return_value = user_info

        self._run(now=datetime(2026, 11, 20, 23, 59, tzinfo=UTC))
        slack.post_message.assert_called_once()

        slack.post_message.reset_mock()
        Incident.objects.update(last_nudge_at=None)
        self._run(now=datetime(2026, 11, 21, 0, 0, tzinfo=UTC))
        slack.post_message.assert_not_called()

    def test_skips_weekends(self, slack):
        self._make_incident()

        self._run(now=datetime(2026, 11, 21, 14, 0, tzinfo=UTC))

        slack.post_message.assert_not_called()

    def test_disabled_by_default(self, slack):
        self._make_incident()

        with patch.dict(settings.SLACK, {"STALE_INCIDENT_NUDGES_ENABLED": False}):
            self._run()

        slack.get_channel_history.assert_not_called()
        slack.post_message.assert_not_called()

    def test_skips_when_channel_history_is_unavailable(self, slack):
        self._make_incident()
        slack.get_channel_history.return_value = []

        self._run()

        slack.post_message.assert_not_called()

    def test_failed_post_does_not_record_nudge(self, slack):
        incident = self._make_incident()
        slack.post_message.return_value = None

        self._run()

        incident.refresh_from_db()
        assert incident.last_nudge_at is None
