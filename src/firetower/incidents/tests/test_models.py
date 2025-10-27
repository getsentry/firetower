import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    Tag,
    TagType,
    filter_visible_to_user,
)


@pytest.mark.django_db
class TestIncident:
    def test_incident_creation(self):
        """Test basic incident creation"""
        user = User.objects.create_user(username="captain@example.com")

        incident = Incident.objects.create(
            title="Test Incident",
            description="Test description",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=user,
        )

        assert incident.title == "Test Incident"
        assert incident.status == "Active"
        assert incident.severity == "P1"
        assert incident.captain == user
        assert incident.id is not None

    def test_incident_id_starts_at_2000(self):
        """Test that incident IDs start at 2000"""
        incident = Incident.objects.create(
            title="First Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P2,
        )

        # Should be 2000 or higher (in case other tests ran first)
        assert incident.id >= 2000

    def test_incident_number_property(self):
        """Test incident_number property returns correct format"""
        incident = Incident.objects.create(
            title="Test", status=IncidentStatus.ACTIVE, severity=IncidentSeverity.P2
        )

        assert incident.incident_number.startswith("INC-")
        assert incident.incident_number == f"INC-{incident.id}"

    def test_incident_str(self):
        """Test incident string representation"""
        incident = Incident.objects.create(
            title="Database Connection Pool Exhausted",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
        )

        expected = f"{incident.incident_number}: Database Connection Pool Exhausted"
        assert str(incident) == expected

    def test_incident_default_ordering(self):
        """Test incidents are ordered by created_at DESC by default"""
        incident1 = Incident.objects.create(
            title="First", status=IncidentStatus.ACTIVE, severity=IncidentSeverity.P1
        )
        incident2 = Incident.objects.create(
            title="Second", status=IncidentStatus.ACTIVE, severity=IncidentSeverity.P1
        )

        incidents = list(Incident.objects.all())
        assert incidents[0] == incident2  # Most recent first
        assert incidents[1] == incident1

    def test_incident_validation_empty_title(self):
        """Test that empty title raises validation error"""
        incident = Incident(
            title="", status=IncidentStatus.ACTIVE, severity=IncidentSeverity.P1
        )

        with pytest.raises(ValidationError) as exc_info:
            incident.save()

        assert "title" in exc_info.value.message_dict

    def test_incident_validation_missing_severity(self):
        """Test that missing severity raises validation error"""
        incident = Incident(title="Test", status=IncidentStatus.ACTIVE)

        with pytest.raises(ValidationError) as exc_info:
            incident.save()

        assert "severity" in exc_info.value.message_dict

    def test_public_incident_visible_to_all(self):
        """Test public incident is visible to everyone"""
        user = User.objects.create_user(username="test@example.com")

        incident = Incident.objects.create(
            title="Public Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P3,
            is_private=False,
        )

        assert incident.is_visible_to_user(user) is True

    def test_private_incident_visible_to_captain(self):
        """Test private incident is visible to captain"""
        captain = User.objects.create_user(username="captain@example.com")
        other_user = User.objects.create_user(username="other@example.com")

        incident = Incident.objects.create(
            title="Private Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
            captain=captain,
        )

        assert incident.is_visible_to_user(captain) is True
        assert incident.is_visible_to_user(other_user) is False

    def test_private_incident_visible_to_reporter(self):
        """Test private incident is visible to reporter"""
        reporter = User.objects.create_user(username="reporter@example.com")
        other_user = User.objects.create_user(username="other@example.com")

        incident = Incident.objects.create(
            title="Private Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
            reporter=reporter,
        )

        assert incident.is_visible_to_user(reporter) is True
        assert incident.is_visible_to_user(other_user) is False

    def test_private_incident_visible_to_participant(self):
        """Test private incident is visible to participant"""
        participant = User.objects.create_user(username="participant@example.com")
        other_user = User.objects.create_user(username="other@example.com")

        incident = Incident.objects.create(
            title="Private Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
        )
        incident.participants.add(participant)

        assert incident.is_visible_to_user(participant) is True
        assert incident.is_visible_to_user(other_user) is False

    def test_private_incident_visible_to_admin(self):
        """Test private incident is visible to admin users"""
        admin_user = User.objects.create_user(username="admin@example.com")
        admin_user.userprofile.is_admin = True
        admin_user.userprofile.save()

        incident = Incident.objects.create(
            title="Private Incident",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
        )

        assert incident.is_visible_to_user(admin_user) is True

    def test_affected_areas_property(self):
        """Test affected_areas property returns list of tag names"""
        incident = Incident.objects.create(
            title="Test", status=IncidentStatus.ACTIVE, severity=IncidentSeverity.P1
        )

        tag1 = Tag.objects.create(name="API", tag_type=TagType.AFFECTED_AREA)
        tag2 = Tag.objects.create(name="Database", tag_type=TagType.AFFECTED_AREA)

        incident.affected_area_tags.add(tag1, tag2)

        areas = incident.affected_areas
        assert len(areas) == 2
        assert "API" in areas
        assert "Database" in areas

    def test_root_causes_property(self):
        """Test root_causes property returns list of tag names"""
        incident = Incident.objects.create(
            title="Test", status=IncidentStatus.ACTIVE, severity=IncidentSeverity.P1
        )

        tag1 = Tag.objects.create(
            name="Resource Exhaustion", tag_type=TagType.ROOT_CAUSE
        )
        tag2 = Tag.objects.create(name="Traffic Spike", tag_type=TagType.ROOT_CAUSE)

        incident.root_cause_tags.add(tag1, tag2)

        causes = incident.root_causes
        assert len(causes) == 2
        assert "Resource Exhaustion" in causes
        assert "Traffic Spike" in causes

    def test_external_links_dict_property(self):
        """Test external_links_dict property returns dict with lowercase keys"""
        incident = Incident.objects.create(
            title="Test", status=IncidentStatus.ACTIVE, severity=IncidentSeverity.P1
        )

        ExternalLink.objects.create(
            incident=incident,
            link_type=ExternalLinkType.SLACK,
            url="https://slack.com/channel",
        )

        links = incident.external_links_dict

        # Should have all link types with None for missing ones
        assert "slack" in links
        assert links["slack"] == "https://slack.com/channel"
        assert links["jira"] is None
        assert links["datadog"] is None


@pytest.mark.django_db
class TestTag:
    def test_tag_creation(self):
        """Test creating a tag"""
        tag = Tag.objects.create(name="API", tag_type=TagType.AFFECTED_AREA)

        assert tag.name == "API"
        assert tag.tag_type == "AFFECTED_AREA"
        assert tag.created_at is not None

    def test_tag_unique_together(self):
        """Test same name can exist for different tag types"""
        Tag.objects.create(name="Database", tag_type=TagType.AFFECTED_AREA)
        Tag.objects.create(name="Database", tag_type=TagType.ROOT_CAUSE)

        assert Tag.objects.filter(name="Database").count() == 2

    def test_tag_unique_constraint(self):
        """Test duplicate name+type combination is not allowed"""
        Tag.objects.create(name="API", tag_type=TagType.AFFECTED_AREA)

        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            Tag.objects.create(name="API", tag_type=TagType.AFFECTED_AREA)

    def test_tag_ordering(self):
        """Test tags are ordered alphabetically by name"""
        Tag.objects.create(name="Zebra", tag_type=TagType.AFFECTED_AREA)
        Tag.objects.create(name="Apple", tag_type=TagType.AFFECTED_AREA)
        Tag.objects.create(name="Banana", tag_type=TagType.AFFECTED_AREA)

        tags = list(Tag.objects.all())
        assert tags[0].name == "Apple"
        assert tags[1].name == "Banana"
        assert tags[2].name == "Zebra"

    def test_tag_str(self):
        """Test tag string representation"""
        tag = Tag.objects.create(name="API", tag_type=TagType.AFFECTED_AREA)

        assert str(tag) == "API (Affected Area)"


@pytest.mark.django_db
class TestExternalLink:
    def test_external_link_creation(self):
        """Test creating external link"""
        incident = Incident.objects.create(
            title="Test", status=IncidentStatus.ACTIVE, severity=IncidentSeverity.P1
        )

        link = ExternalLink.objects.create(
            incident=incident,
            link_type=ExternalLinkType.SLACK,
            url="https://slack.com/channel",
        )

        assert link.incident == incident
        assert link.link_type == "SLACK"
        assert link.url == "https://slack.com/channel"
        assert link.created_at is not None

    def test_external_link_unique_together(self):
        """Test incident can only have one link per type"""
        incident = Incident.objects.create(
            title="Test", status=IncidentStatus.ACTIVE, severity=IncidentSeverity.P1
        )

        ExternalLink.objects.create(
            incident=incident,
            link_type=ExternalLinkType.SLACK,
            url="https://slack.com/channel1",
        )

        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            ExternalLink.objects.create(
                incident=incident,
                link_type=ExternalLinkType.SLACK,
                url="https://slack.com/channel2",
            )

    def test_external_link_multiple_types(self):
        """Test incident can have multiple links of different types"""
        incident = Incident.objects.create(
            title="Test", status=IncidentStatus.ACTIVE, severity=IncidentSeverity.P1
        )

        slack = ExternalLink.objects.create(
            incident=incident, link_type=ExternalLinkType.SLACK, url="https://slack.com"
        )

        jira = ExternalLink.objects.create(
            incident=incident, link_type=ExternalLinkType.JIRA, url="https://jira.com"
        )

        assert incident.external_links.count() == 2
        assert slack in incident.external_links.all()
        assert jira in incident.external_links.all()

    def test_external_link_str(self):
        """Test external link string representation"""
        incident = Incident.objects.create(
            title="Test", status=IncidentStatus.ACTIVE, severity=IncidentSeverity.P1
        )

        link = ExternalLink.objects.create(
            incident=incident, link_type=ExternalLinkType.SLACK, url="https://slack.com"
        )

        assert str(link) == f"{incident.incident_number} - SLACK"


@pytest.mark.django_db
class TestFilterVisibleToUser:
    def test_admin_sees_all_incidents(self):
        """Test admin users see all incidents"""
        admin = User.objects.create_user(username="admin@example.com")
        admin.userprofile.is_admin = True
        admin.userprofile.save()

        public = Incident.objects.create(
            title="Public",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=False,
        )

        private = Incident.objects.create(
            title="Private",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
        )

        queryset = Incident.objects.all()
        filtered = filter_visible_to_user(queryset, admin)

        assert filtered.count() == 2
        assert public in filtered
        assert private in filtered

    def test_regular_user_sees_public_and_own_private(self):
        """Test regular users see public incidents and their own private ones"""
        user = User.objects.create_user(username="user@example.com")
        other_user = User.objects.create_user(username="other@example.com")

        public = Incident.objects.create(
            title="Public",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=False,
        )

        user_private = Incident.objects.create(
            title="User Private",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
            captain=user,
        )

        other_private = Incident.objects.create(
            title="Other Private",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
            captain=other_user,
        )

        queryset = Incident.objects.all()
        filtered = filter_visible_to_user(queryset, user)

        assert filtered.count() == 2
        assert public in filtered
        assert user_private in filtered
        assert other_private not in filtered

    def test_participant_sees_private_incident(self):
        """Test participants can see private incidents they're involved in"""
        participant = User.objects.create_user(username="participant@example.com")
        other_user = User.objects.create_user(username="other@example.com")

        private = Incident.objects.create(
            title="Private",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
        )
        private.participants.add(participant)

        other_private = Incident.objects.create(
            title="Other Private",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            is_private=True,
            captain=other_user,
        )

        queryset = Incident.objects.all()
        filtered = filter_visible_to_user(queryset, participant)

        assert filtered.count() == 1
        assert private in filtered
        assert other_private not in filtered
