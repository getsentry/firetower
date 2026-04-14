from firetower.slack_app.handlers.utils import get_incident_from_channel

from .conftest import CHANNEL_ID


class TestGetIncidentFromChannel:
    def test_returns_incident(self, incident):
        result = get_incident_from_channel(CHANNEL_ID)
        assert result == incident

    def test_returns_none_for_unknown_channel(self, db):
        result = get_incident_from_channel("C_UNKNOWN")
        assert result is None

    def test_returns_none_when_no_incidents(self, db):
        result = get_incident_from_channel(CHANNEL_ID)
        assert result is None
