from django.db import models
from django.db.models import Q, QuerySet

from firetower.incidents.models import Incident


class ExternalProfileType(models.TextChoices):
    IAP = "IAP", "IAP"
    SLACK = "SLACK", "Slack"
    PAGERDUTY = "PAGERDUTY", "PagerDuty"
    LINEAR = "LINEAR", "Linear"
    DATADOG = "DATADOG", "Datadog"


class UserProfile(models.Model):
    """
    Extended profile for users.

    Linked to Django's built-in User model which provides:
    - username (set to user's email)
    - email
    - first_name
    - last_name
    - is_superuser (for admin access)

    External identities (IAP, Slack, etc.) are stored in ExternalProfile.
    """

    user = models.OneToOneField(
        "auth.User", on_delete=models.CASCADE, related_name="userprofile"
    )
    avatar_url = models.URLField(blank=True)

    @property
    def user_incidents(self) -> QuerySet[Incident]:
        """Return all incidents where user is captain, reporter, or participant"""

        return Incident.objects.filter(
            Q(captain=self.user) | Q(reporter=self.user) | Q(participants=self.user)
        ).distinct()

    def get_external_profile(self, profile_type: str) -> "ExternalProfile | None":
        """
        Get external profile by type.

        Args:
            profile_type: ExternalProfileType value (e.g., 'SLACK')

        Returns:
            ExternalProfile instance or None
        """
        return self.user.external_profiles.filter(type=profile_type).first()

    def get_slack_id(self) -> str | None:
        """Convenience method for getting Slack user ID"""
        profile = self.get_external_profile(ExternalProfileType.SLACK)
        return profile.external_id if profile else None

    def get_pagerduty_id(self) -> str | None:
        """Convenience method for getting PagerDuty user ID"""
        profile = self.get_external_profile(ExternalProfileType.PAGERDUTY)
        return profile.external_id if profile else None

    def get_iap_id(self) -> str | None:
        """Convenience method for getting IAP user ID"""
        profile = self.get_external_profile(ExternalProfileType.IAP)
        return profile.external_id if profile else None

    def __str__(self) -> str:
        return self.user.get_full_name() or self.user.email


class ExternalProfile(models.Model):
    """
    Links users to their profiles in external services.

    Examples:
    - Slack user ID (U12345)
    - PagerDuty user ID (PXXXXXX)
    - Linear user ID
    """

    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, related_name="external_profiles"
    )
    type = models.CharField(max_length=20, choices=ExternalProfileType.choices)
    external_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "type")]
        indexes = [
            models.Index(fields=["type", "external_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} - {self.type}: {self.external_id}"
