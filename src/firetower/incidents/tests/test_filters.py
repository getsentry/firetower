from datetime import datetime

import pytest
from django.contrib.auth.models import User
from django.utils import timezone as django_timezone
from rest_framework.test import APIClient

from firetower.incidents.models import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    ServiceTier,
    Tag,
    TagType,
)


@pytest.mark.django_db
class TestUIIncidentFilters:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            password="testpass123",
        )

    def test_filter_by_status(self):
        Incident.objects.create(
            title="Active Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.create(
            title="Mitigated Incident",
            status=IncidentStatus.MITIGATED,
            severity=IncidentSeverity.P2,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/?status=Active")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["title"] == "Active Incident"

    def test_filter_by_multiple_statuses(self):
        Incident.objects.create(
            title="Active",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.create(
            title="Mitigated",
            status=IncidentStatus.MITIGATED,
            severity=IncidentSeverity.P2,
        )
        Incident.objects.create(
            title="Done",
            status=IncidentStatus.DONE,
            severity=IncidentSeverity.P3,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/?status=Active&status=Mitigated")

        assert response.status_code == 200
        assert response.data["count"] == 2
        assert len(response.data["results"]) == 2

    def test_filter_by_created_after(self):
        inc1 = Incident.objects.create(
            title="Old Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        inc2 = Incident.objects.create(
            title="New Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.filter(pk=inc1.pk).update(
            created_at=datetime(2024, 1, 1, 0, 0, 0)
        )
        Incident.objects.filter(pk=inc2.pk).update(
            created_at=datetime(2024, 6, 15, 12, 0, 0)
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/?created_after=2024-06-01")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "New Incident"

    def test_filter_by_created_before(self):
        inc1 = Incident.objects.create(
            title="Old Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        inc2 = Incident.objects.create(
            title="New Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.filter(pk=inc1.pk).update(
            created_at=datetime(2024, 1, 1, 0, 0, 0)
        )
        Incident.objects.filter(pk=inc2.pk).update(
            created_at=datetime(2024, 6, 15, 12, 0, 0)
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/?created_before=2024-06-01")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Old Incident"

    def test_filter_by_date_range(self):
        inc1 = Incident.objects.create(
            title="Too Old",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        inc2 = Incident.objects.create(
            title="In Range",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        inc3 = Incident.objects.create(
            title="Too New",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.filter(pk=inc1.pk).update(
            created_at=datetime(2024, 1, 1, 0, 0, 0)
        )
        Incident.objects.filter(pk=inc2.pk).update(
            created_at=datetime(2024, 6, 15, 12, 0, 0)
        )
        Incident.objects.filter(pk=inc3.pk).update(
            created_at=datetime(2024, 12, 1, 0, 0, 0)
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            "/api/ui/incidents/?created_after=2024-06-01&created_before=2024-07-01"
        )

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "In Range"

    def test_filter_by_datetime_with_time(self):
        inc = Incident.objects.create(
            title="Test",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.filter(pk=inc.pk).update(
            created_at=datetime(2024, 6, 15, 14, 30, 0)
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/api/ui/incidents/?created_after=2024-06-15T14:00:00"
        )
        assert response.status_code == 200
        assert response.data["count"] == 1

        response = self.client.get(
            "/api/ui/incidents/?created_after=2024-06-15T15:00:00"
        )
        assert response.status_code == 200
        assert response.data["count"] == 0

    def test_filter_by_datetime_with_timezone(self):
        inc = Incident.objects.create(
            title="Test",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.filter(pk=inc.pk).update(
            created_at=django_timezone.make_aware(datetime(2024, 6, 15, 14, 0, 0))
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/api/ui/incidents/?created_after=2024-06-15T14:00:00Z"
        )
        assert response.status_code == 200
        assert response.data["count"] == 1

        response = self.client.get(
            "/api/ui/incidents/?created_after=2024-06-15T10:00:00-04:00"
        )
        assert response.status_code == 200
        assert response.data["count"] == 1

        response = self.client.get(
            "/api/ui/incidents/?created_after=2024-06-15T06:00:00-08:00"
        )
        assert response.status_code == 200
        assert response.data["count"] == 1

        response = self.client.get(
            "/api/ui/incidents/?created_after=2024-06-15T07:00:00-08:00"
        )
        assert response.status_code == 200
        assert response.data["count"] == 0

    def test_invalid_date_format(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/ui/incidents/?created_after=invalid-date")
        assert response.status_code == 400
        assert "created_after" in response.data

        response = self.client.get("/api/ui/incidents/?created_before=not-a-date")
        assert response.status_code == 400
        assert "created_before" in response.data

    def test_filter_by_severity(self):
        Incident.objects.create(
            title="P1 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.create(
            title="P2 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P2,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/?severity=P1")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["title"] == "P1 Incident"

    def test_filter_by_multiple_severities(self):
        Incident.objects.create(
            title="P1 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.create(
            title="P2 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P2,
        )
        Incident.objects.create(
            title="P3 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P3,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/?severity=P1&severity=P2")

        assert response.status_code == 200
        assert response.data["count"] == 2
        assert len(response.data["results"]) == 2

    def test_filter_by_severity_and_status(self):
        Incident.objects.create(
            title="Active P1",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.create(
            title="Mitigated P1",
            status=IncidentStatus.MITIGATED,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.create(
            title="Active P2",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P2,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/?severity=P1&status=Active")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["title"] == "Active P1"

    def test_filter_by_tag(self):
        inc1 = Incident.objects.create(
            title="API Down",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        inc2 = Incident.objects.create(
            title="DB Down",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        tag_api = Tag.objects.create(name="API", type=TagType.AFFECTED_SERVICE)
        tag_db = Tag.objects.create(name="Database", type=TagType.AFFECTED_SERVICE)
        inc1.affected_service_tags.add(tag_api)
        inc2.affected_service_tags.add(tag_db)

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/?affected_service=API")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "API Down"

    def test_filter_by_multiple_tags_same_type(self):
        inc1 = Incident.objects.create(
            title="API Down",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        inc2 = Incident.objects.create(
            title="DB Down",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        inc3 = Incident.objects.create(
            title="Cache Down",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        tag_api = Tag.objects.create(name="API", type=TagType.AFFECTED_SERVICE)
        tag_db = Tag.objects.create(name="Database", type=TagType.AFFECTED_SERVICE)
        tag_cache = Tag.objects.create(name="Cache", type=TagType.AFFECTED_SERVICE)
        inc1.affected_service_tags.add(tag_api)
        inc2.affected_service_tags.add(tag_db)
        inc3.affected_service_tags.add(tag_cache)

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            "/api/ui/incidents/?affected_service=API&affected_service=Database"
        )

        assert response.status_code == 200
        assert response.data["count"] == 2

    def test_filter_by_tags_across_types(self):
        inc1 = Incident.objects.create(
            title="API OOM",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        inc2 = Incident.objects.create(
            title="API Config",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        tag_api = Tag.objects.create(name="API", type=TagType.AFFECTED_SERVICE)
        tag_oom = Tag.objects.create(name="OOM", type=TagType.ROOT_CAUSE)
        tag_config = Tag.objects.create(name="Config", type=TagType.ROOT_CAUSE)
        inc1.affected_service_tags.add(tag_api)
        inc1.root_cause_tags.add(tag_oom)
        inc2.affected_service_tags.add(tag_api)
        inc2.root_cause_tags.add(tag_config)

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            "/api/ui/incidents/?affected_service=API&root_cause=OOM"
        )

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "API OOM"

    def test_filter_by_service_tier(self):
        Incident.objects.create(
            title="T0 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            service_tier=ServiceTier.T0,
        )
        Incident.objects.create(
            title="T1 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P2,
            service_tier=ServiceTier.T1,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/?service_tier=T0")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "T0 Incident"

    def test_filter_by_multiple_service_tiers(self):
        Incident.objects.create(
            title="T0 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            service_tier=ServiceTier.T0,
        )
        Incident.objects.create(
            title="T1 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P2,
            service_tier=ServiceTier.T1,
        )
        Incident.objects.create(
            title="T2 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P3,
            service_tier=ServiceTier.T2,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/?service_tier=T0&service_tier=T1")

        assert response.status_code == 200
        assert response.data["count"] == 2

    def test_filter_by_captain(self):
        captain1 = User.objects.create_user(
            username="captain1@example.com",
            email="captain1@example.com",
        )
        captain2 = User.objects.create_user(
            username="captain2@example.com",
            email="captain2@example.com",
        )
        Incident.objects.create(
            title="Captain1 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=captain1,
        )
        Incident.objects.create(
            title="Captain2 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=captain2,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/?captain=captain1@example.com")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Captain1 Incident"

    def test_filter_by_reporter(self):
        reporter1 = User.objects.create_user(
            username="reporter1@example.com",
            email="reporter1@example.com",
        )
        reporter2 = User.objects.create_user(
            username="reporter2@example.com",
            email="reporter2@example.com",
        )
        Incident.objects.create(
            title="Reporter1 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            reporter=reporter1,
        )
        Incident.objects.create(
            title="Reporter2 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            reporter=reporter2,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/ui/incidents/?reporter=reporter1@example.com")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Reporter1 Incident"


@pytest.mark.django_db
class TestServiceAPIIncidentFilters:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            password="testpass123",
        )
        self.captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            password="testpass123",
        )
        self.reporter = User.objects.create_user(
            username="reporter@example.com",
            email="reporter@example.com",
            password="testpass123",
        )

    def test_filter_by_date_range(self):
        inc1 = Incident.objects.create(
            title="Old Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        inc2 = Incident.objects.create(
            title="New Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.filter(pk=inc1.pk).update(
            created_at=datetime(2024, 1, 1, 0, 0, 0)
        )
        Incident.objects.filter(pk=inc2.pk).update(
            created_at=datetime(2024, 6, 15, 12, 0, 0)
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/incidents/?created_after=2024-06-01")
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "New Incident"

        response = self.client.get("/api/incidents/?created_before=2024-06-01")
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Old Incident"

        response = self.client.get(
            "/api/incidents/?created_after=2024-06-01&created_before=2024-07-01"
        )
        assert response.status_code == 200
        assert response.data["count"] == 1

    def test_invalid_date_format(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/incidents/?created_after=invalid")
        assert response.status_code == 400
        assert "created_after" in response.data

    def test_filter_by_severity(self):
        Incident.objects.create(
            title="P1 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.create(
            title="P2 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P2,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/incidents/?severity=P1")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["title"] == "P1 Incident"

    def test_filter_by_multiple_severities(self):
        Incident.objects.create(
            title="P1 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.create(
            title="P2 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P2,
        )
        Incident.objects.create(
            title="P3 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P3,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/incidents/?severity=P1&severity=P2")

        assert response.status_code == 200
        assert response.data["count"] == 2
        assert len(response.data["results"]) == 2

    def test_invalid_severity(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/incidents/?severity=InvalidSeverity")
        assert response.status_code == 400
        assert "severity" in response.data

    def test_filter_by_severity_and_date(self):
        Incident.objects.create(
            title="P1 Old",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.create(
            title="P1 New",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.create(
            title="P2 Old",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P2,
        )
        Incident.objects.filter(pk=Incident.objects.get(title="P1 Old").pk).update(
            created_at=datetime(2024, 1, 1, 0, 0, 0)
        )
        Incident.objects.filter(pk=Incident.objects.get(title="P2 Old").pk).update(
            created_at=datetime(2024, 1, 1, 0, 0, 0)
        )
        Incident.objects.filter(pk=Incident.objects.get(title="P1 New").pk).update(
            created_at=datetime(2024, 6, 15, 12, 0, 0)
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            "/api/incidents/?severity=P1&created_after=2024-01-01"
        )

        assert response.status_code == 200
        assert response.data["count"] == 2
        assert len(response.data["results"]) == 2

    def test_filter_by_tag(self):
        inc1 = Incident.objects.create(
            title="API Down",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        inc2 = Incident.objects.create(
            title="DB Down",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        tag_api = Tag.objects.create(name="API", type=TagType.AFFECTED_SERVICE)
        tag_db = Tag.objects.create(name="Database", type=TagType.AFFECTED_SERVICE)
        inc1.affected_service_tags.add(tag_api)
        inc2.affected_service_tags.add(tag_db)

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/incidents/?affected_service=API")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "API Down"

    def test_filter_by_tags_across_types(self):
        inc1 = Incident.objects.create(
            title="API OOM",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        inc2 = Incident.objects.create(
            title="API Config",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        tag_api = Tag.objects.create(name="API", type=TagType.AFFECTED_SERVICE)
        tag_oom = Tag.objects.create(name="OOM", type=TagType.ROOT_CAUSE)
        tag_config = Tag.objects.create(name="Config", type=TagType.ROOT_CAUSE)
        inc1.affected_service_tags.add(tag_api)
        inc1.root_cause_tags.add(tag_oom)
        inc2.affected_service_tags.add(tag_api)
        inc2.root_cause_tags.add(tag_config)

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            "/api/incidents/?affected_service=API&root_cause=OOM"
        )

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "API OOM"

    def test_filter_by_status(self):
        Incident.objects.create(
            title="Active Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )
        Incident.objects.create(
            title="Done Incident",
            status=IncidentStatus.DONE,
            severity=IncidentSeverity.P1,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/incidents/?status=Active")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Active Incident"

    def test_invalid_status(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/incidents/?status=InvalidStatus")
        assert response.status_code == 400
        assert "status" in response.data

    def test_invalid_service_tier(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/incidents/?service_tier=InvalidTier")
        assert response.status_code == 400
        assert "service_tier" in response.data

    def test_filter_by_service_tier(self):
        Incident.objects.create(
            title="T0 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            service_tier=ServiceTier.T0,
        )
        Incident.objects.create(
            title="T1 Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            service_tier=ServiceTier.T1,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/incidents/?service_tier=T0")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "T0 Incident"

    def test_filter_by_captain(self):
        Incident.objects.create(
            title="Captain Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=self.captain,
        )
        Incident.objects.create(
            title="Other Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=self.reporter,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/incidents/?captain=captain@example.com")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Captain Incident"

    def test_filter_by_reporter(self):
        Incident.objects.create(
            title="Reporter Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            reporter=self.reporter,
        )
        Incident.objects.create(
            title="Other Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            reporter=self.captain,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/incidents/?reporter=reporter@example.com")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Reporter Incident"
