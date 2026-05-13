from unittest.mock import MagicMock

import pytest
from django.contrib.auth.models import User

from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from firetower.slack_app.handlers.list_incidents import handle_list_command


@pytest.mark.django_db
class TestListCommand:
    def test_no_incidents_responds_empty_message(self, db):
        ack = MagicMock()
        body = {"channel_id": "C_ANY"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_list_command(ack, body, command, respond)

        ack.assert_called_once()
        assert "No active or mitigated incidents" in respond.call_args[0][0]

    def test_active_incidents_shown(self, db):
        captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Jane",
            last_name="Doe",
        )
        inc = Incident(
            title="DB is on fire",
            severity=IncidentSeverity.P1,
            status=IncidentStatus.ACTIVE,
            captain=captain,
        )
        inc.save()
        ExternalLink.objects.create(
            incident=inc,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C_INC",
        )

        ack = MagicMock()
        body = {"channel_id": "C_ANY"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_list_command(ack, body, command, respond)

        text = respond.call_args[0][0]
        assert "*Active Incidents*" in text
        assert "P1" in text
        assert "DB is on fire" in text
        assert "Jane Doe" in text
        assert "<https://slack.com/archives/C_INC|Slack>" in text

    def test_mitigated_incidents_shown(self, db):
        inc = Incident(
            title="Mitigated issue",
            severity=IncidentSeverity.P2,
            status=IncidentStatus.MITIGATED,
        )
        inc.save()

        ack = MagicMock()
        body = {"channel_id": "C_ANY"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_list_command(ack, body, command, respond)

        text = respond.call_args[0][0]
        assert "*Mitigated Incidents*" in text
        assert "P2" in text
        assert "Mitigated issue" in text
        assert "unassigned" in text

    def test_private_incidents_excluded(self, db):
        inc = Incident(
            title="Secret incident",
            severity=IncidentSeverity.P0,
            status=IncidentStatus.ACTIVE,
            is_private=True,
        )
        inc.save()

        ack = MagicMock()
        body = {"channel_id": "C_ANY"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_list_command(ack, body, command, respond)

        assert "No active or mitigated incidents" in respond.call_args[0][0]

    def test_done_and_cancelled_excluded(self, db):
        for status in (
            IncidentStatus.DONE,
            IncidentStatus.CANCELLED,
            IncidentStatus.POSTMORTEM,
        ):
            inc = Incident(
                title=f"Inc {status}",
                severity=IncidentSeverity.P3,
                status=status,
            )
            inc.save()

        ack = MagicMock()
        body = {"channel_id": "C_ANY"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_list_command(ack, body, command, respond)

        assert "No active or mitigated incidents" in respond.call_args[0][0]

    def test_grouped_active_before_mitigated(self, db):
        active = Incident(
            title="Active one",
            severity=IncidentSeverity.P2,
            status=IncidentStatus.ACTIVE,
        )
        active.save()
        mitigated = Incident(
            title="Mitigated one",
            severity=IncidentSeverity.P1,
            status=IncidentStatus.MITIGATED,
        )
        mitigated.save()

        ack = MagicMock()
        body = {"channel_id": "C_ANY"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_list_command(ack, body, command, respond)

        text = respond.call_args[0][0]
        active_pos = text.index("*Active Incidents*")
        mitigated_pos = text.index("*Mitigated Incidents*")
        assert active_pos < mitigated_pos

    def test_no_slack_link_omits_link(self, db):
        inc = Incident(
            title="No slack link",
            severity=IncidentSeverity.P3,
            status=IncidentStatus.ACTIVE,
        )
        inc.save()

        ack = MagicMock()
        body = {"channel_id": "C_ANY"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_list_command(ack, body, command, respond)

        text = respond.call_args[0][0]
        assert "No slack link" in text
        assert "Slack>" not in text

    def test_newest_first_within_group(self, db):
        older = Incident(
            title="Older incident",
            severity=IncidentSeverity.P2,
            status=IncidentStatus.ACTIVE,
        )
        older.save()
        newer = Incident(
            title="Newer incident",
            severity=IncidentSeverity.P2,
            status=IncidentStatus.ACTIVE,
        )
        newer.save()

        ack = MagicMock()
        body = {"channel_id": "C_ANY"}
        command = {"command": "/ft"}
        respond = MagicMock()

        handle_list_command(ack, body, command, respond)

        text = respond.call_args[0][0]
        newer_pos = text.index("Newer incident")
        older_pos = text.index("Older incident")
        assert newer_pos < older_pos
