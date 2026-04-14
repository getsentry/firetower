import pytest
from django.contrib.auth.models import User

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
)

CHANNEL_ID = "C_TEST_CHANNEL"


@pytest.fixture
def user(db):
    u = User.objects.create_user(
        username="test@example.com",
        email="test@example.com",
        first_name="Test",
        last_name="User",
    )
    ExternalProfile.objects.create(
        user=u,
        type=ExternalProfileType.SLACK,
        external_id="U_CAPTAIN",
    )
    return u


@pytest.fixture
def incident(user):
    inc = Incident(
        title="Test Incident",
        severity=IncidentSeverity.P2,
        status=IncidentStatus.ACTIVE,
        captain=user,
        reporter=user,
    )
    inc.save()
    ExternalLink.objects.create(
        incident=inc,
        type=ExternalLinkType.SLACK,
        url="https://slack.com/archives/C_TEST_CHANNEL",
    )
    return inc
