import pytest
from django.contrib.auth.models import User

from firetower.auth.models import ExternalProfile, ExternalProfileType, UserProfile


@pytest.mark.django_db
class TestUserProfile:
    def test_userprofile_auto_created_on_user_creation(self):
        """Test that UserProfile is automatically created when User is created"""
        user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

        assert hasattr(user, "userprofile")
        assert isinstance(user.userprofile, UserProfile)
        assert user.userprofile.avatar_url == ""

    def test_userprofile_str(self):
        """Test UserProfile string representation"""
        user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
        )

        assert str(user.userprofile) == "John Doe"

    def test_userprofile_str_fallback_to_email(self):
        """Test UserProfile falls back to email if no full name"""
        user = User.objects.create_user(
            username="iap_user_id_123", email="test@example.com"
        )

        assert str(user.userprofile) == "test@example.com"

    def test_user_incidents_property(self):
        """Test UserProfile.user_incidents returns incidents user is involved in"""
        from firetower.incidents.models import (
            Incident,
            IncidentSeverity,
            IncidentStatus,
        )

        user = User.objects.create_user(username="test@example.com")
        other_user = User.objects.create_user(username="other@example.com")

        # Incident where user is captain
        incident1 = Incident.objects.create(
            title="As Captain",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=user,
        )

        # Incident where user is reporter
        incident2 = Incident.objects.create(
            title="As Reporter",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P2,
            reporter=user,
        )

        # Incident where user is participant
        incident3 = Incident.objects.create(
            title="As Participant",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P3,
        )
        incident3.participants.add(user)

        # Incident user is not involved in
        incident4 = Incident.objects.create(
            title="Not Involved",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P4,
            captain=other_user,
        )

        # Check user_incidents property
        user_incident_ids = set(
            user.userprofile.user_incidents.values_list("id", flat=True)
        )
        assert len(user_incident_ids) == 3
        assert incident1.id in user_incident_ids
        assert incident2.id in user_incident_ids
        assert incident3.id in user_incident_ids
        assert incident4.id not in user_incident_ids

    def test_get_external_profile(self):
        """Test getting external profile by type"""
        user = User.objects.create_user(username="test@example.com")

        # Create Slack profile
        slack_profile = ExternalProfile.objects.create(
            user=user, type=ExternalProfileType.SLACK, external_id="U12345"
        )

        # Test generic method
        retrieved = user.userprofile.get_external_profile(ExternalProfileType.SLACK)
        assert retrieved == slack_profile
        assert retrieved.external_id == "U12345"

        # Test non-existent profile
        assert (
            user.userprofile.get_external_profile(ExternalProfileType.PAGERDUTY) is None
        )

    def test_get_slack_id(self):
        """Test convenience method for getting Slack ID"""
        user = User.objects.create_user(username="test@example.com")

        # No Slack profile
        assert user.userprofile.get_slack_id() is None

        # Create Slack profile
        ExternalProfile.objects.create(
            user=user, type=ExternalProfileType.SLACK, external_id="U12345"
        )

        assert user.userprofile.get_slack_id() == "U12345"

    def test_get_pagerduty_id(self):
        """Test convenience method for getting PagerDuty ID"""
        user = User.objects.create_user(username="test@example.com")

        # No PagerDuty profile
        assert user.userprofile.get_pagerduty_id() is None

        # Create PagerDuty profile
        ExternalProfile.objects.create(
            user=user, type=ExternalProfileType.PAGERDUTY, external_id="PXXXXXX"
        )

        assert user.userprofile.get_pagerduty_id() == "PXXXXXX"


@pytest.mark.django_db
class TestExternalProfile:
    def test_external_profile_creation(self):
        """Test creating external profile"""
        user = User.objects.create_user(username="test@example.com")

        profile = ExternalProfile.objects.create(
            user=user, type=ExternalProfileType.SLACK, external_id="U12345"
        )

        assert profile.user == user
        assert profile.type == "SLACK"
        assert profile.external_id == "U12345"
        assert profile.created_at is not None

    def test_external_profile_unique_together(self):
        """Test that user can only have one profile per type"""
        user = User.objects.create_user(username="test@example.com")

        # Create first Slack profile
        ExternalProfile.objects.create(
            user=user, type=ExternalProfileType.SLACK, external_id="U12345"
        )

        # Try to create second Slack profile - should fail
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            ExternalProfile.objects.create(
                user=user, type=ExternalProfileType.SLACK, external_id="U99999"
            )

    def test_multiple_types_allowed(self):
        """Test that user can have multiple profiles of different types"""
        user = User.objects.create_user(username="test@example.com")

        slack = ExternalProfile.objects.create(
            user=user, type=ExternalProfileType.SLACK, external_id="U12345"
        )

        pagerduty = ExternalProfile.objects.create(
            user=user, type=ExternalProfileType.PAGERDUTY, external_id="PXXXXXX"
        )

        assert user.external_profiles.count() == 2
        assert slack in user.external_profiles.all()
        assert pagerduty in user.external_profiles.all()

    def test_reverse_lookup_by_external_id(self):
        """Test finding user by their external ID"""
        user = User.objects.create_user(username="test@example.com")

        ExternalProfile.objects.create(
            user=user, type=ExternalProfileType.SLACK, external_id="U12345"
        )

        # Find user by Slack ID
        profile = ExternalProfile.objects.get(
            type=ExternalProfileType.SLACK, external_id="U12345"
        )

        assert profile.user == user

    def test_external_profile_str(self):
        """Test ExternalProfile string representation"""
        user = User.objects.create_user(username="test@example.com")

        profile = ExternalProfile.objects.create(
            user=user, type=ExternalProfileType.SLACK, external_id="U12345"
        )

        assert str(profile) == "test@example.com - SLACK: U12345"
