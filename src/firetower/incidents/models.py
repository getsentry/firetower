from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractUser, User
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q, QuerySet

INCIDENT_ID_START = 2000


class IncidentCounter(models.Model):
    """Stores the next available incident ID for gapless sequencing."""

    next_id = models.PositiveIntegerField(default=INCIDENT_ID_START)

    class Meta:
        db_table = "incidents_incident_counter"


def get_next_incident_id() -> int:
    """Atomically get and increment the incident ID counter."""
    with transaction.atomic():
        try:
            counter = IncidentCounter.objects.select_for_update().get(pk=1)
        except IncidentCounter.DoesNotExist:
            # Self-heal: recreate counter from existing incidents.
            # get_or_create handles the race condition where two threads both
            # hit DoesNotExist - one succeeds at create, other retries get.
            max_id = Incident.objects.aggregate(max_id=models.Max("id"))["max_id"]
            counter, _ = IncidentCounter.objects.get_or_create(
                pk=1,
                defaults={"next_id": (max_id + 1) if max_id else INCIDENT_ID_START},
            )
            # Re-lock the row after get_or_create
            counter = IncidentCounter.objects.select_for_update().get(pk=1)
        next_id = counter.next_id
        counter.next_id += 1
        counter.save()
        return next_id


class IncidentStatus(models.TextChoices):
    ACTIVE = "Active", "Active"
    MITIGATED = "Mitigated", "Mitigated"
    POSTMORTEM = "Postmortem", "Postmortem"
    DONE = "Done", "Done"


class IncidentSeverity(models.TextChoices):
    P0 = "P0", "P0"
    P1 = "P1", "P1"
    P2 = "P2", "P2"
    P3 = "P3", "P3"
    P4 = "P4", "P4"


class ServiceTier(models.TextChoices):
    T0 = "T0", "T0"
    T1 = "T1", "T1"
    T2 = "T2", "T2"
    T3 = "T3", "T3"
    T4 = "T4", "T4"


class TagType(models.TextChoices):
    AFFECTED_SERVICE = "AFFECTED_SERVICE", "Affected Service"
    ROOT_CAUSE = "ROOT_CAUSE", "Root Cause"
    IMPACT_TYPE = "IMPACT_TYPE", "Impact Type"


class ExternalLinkType(models.TextChoices):
    SLACK = "SLACK", "Slack"
    JIRA = "JIRA", "Jira"
    DATADOG = "DATADOG", "Datadog"
    PAGERDUTY = "PAGERDUTY", "PagerDuty"
    STATUSPAGE = "STATUSPAGE", "StatusPage"
    NOTION = "NOTION", "Notion"
    LINEAR = "LINEAR", "Linear"


class Tag(models.Model):
    """
    Tag for categorizing incidents.

    type determines if this is an affected service or root cause.
    Same name can exist for both types (e.g., "Database").

    Names preserve original casing but are case-insensitive unique.
    """

    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=TagType.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("name", "type")]
        ordering = ["name"]

    def clean(self) -> None:
        """Validate case-insensitive uniqueness"""

        if self.name:
            # Check for case-insensitive duplicates
            existing = Tag.objects.filter(
                name__iexact=self.name, type=self.type
            ).exclude(pk=self.pk)

            if existing.exists():
                first_tag = existing.first()
                assert first_tag is not None
                raise ValidationError(
                    {
                        "name": f'Tag "{first_tag.name}" already exists for this type (case-insensitive match)'
                    }
                )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Run validation before saving"""
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.get_type_display()})"


class Incident(models.Model):
    """
    Core incident model.

    The id field is the numeric identifier (2000, 2001, etc.) and is exposed
    as "INC-{id}" via the incident_number property.
    """

    # Primary key - numeric ID (2000, 2001, etc.)
    # Uses IncidentCounter for gapless sequential IDs
    id = models.PositiveIntegerField(primary_key=True)

    # Core fields
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    impact_summary = models.TextField(blank=True)

    # Status and severity
    status = models.CharField(
        max_length=20, choices=IncidentStatus.choices, default=IncidentStatus.ACTIVE
    )
    severity = models.CharField(max_length=2, choices=IncidentSeverity.choices)
    service_tier = models.CharField(
        max_length=2, choices=ServiceTier.choices, null=True, blank=True
    )

    # Privacy
    is_private = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    participants_last_synced_at = models.DateTimeField(null=True, blank=True)

    # Milestone timestamps (for postmortem)
    time_started = models.DateTimeField(null=True, blank=True)
    time_detected = models.DateTimeField(null=True, blank=True)
    time_analyzed = models.DateTimeField(null=True, blank=True)
    time_mitigated = models.DateTimeField(null=True, blank=True)
    time_recovered = models.DateTimeField(null=True, blank=True)

    # Relationships
    captain = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidents_as_captain",
    )
    reporter = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidents_as_reporter",
    )
    participants = models.ManyToManyField(
        "auth.User", blank=True, related_name="incidents_as_participant"
    )

    # Tags (many-to-many)
    # Django ManyToManyField descriptor type is too complex for mypy (var-annotated)
    affected_service_tags = models.ManyToManyField(  # type: ignore[var-annotated]
        "Tag",
        blank=True,
        related_name="incidents_by_affected_service",
        limit_choices_to={"type": "AFFECTED_SERVICE"},
    )
    root_cause_tags = models.ManyToManyField(  # type: ignore[var-annotated]
        "Tag",
        blank=True,
        related_name="incidents_by_root_cause",
        limit_choices_to={"type": "ROOT_CAUSE"},
    )
    impact_type_tags = models.ManyToManyField(  # type: ignore[var-annotated]
        "Tag",
        blank=True,
        related_name="incidents_by_impact_type",
        limit_choices_to={"type": "IMPACT_TYPE"},
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["severity", "-created_at"]),
        ]

    @property
    def incident_number(self) -> str:
        """Return formatted incident number (e.g., 'INC-2000')"""

        return f"{settings.PROJECT_KEY}-{self.id}"

    @property
    def affected_service_tag_names(self) -> list[str]:
        """Return list of affected service names (uses prefetch cache if available)"""
        return [tag.name for tag in self.affected_service_tags.all()]

    @property
    def root_cause_tag_names(self) -> list[str]:
        """Return list of root cause names (uses prefetch cache if available)"""
        return [tag.name for tag in self.root_cause_tags.all()]

    @property
    def impact_type_tag_names(self) -> list[str]:
        """Return list of impact type tag names (uses prefetch cache if available)"""
        return [tag.name for tag in self.impact_type_tags.all()]

    @property
    def external_links_dict(self) -> dict[str, str]:
        """Return external links as dict with lowercase keys (only includes existing links)"""
        links: dict[str, str] = {}
        for link in self.external_links.all():
            links[link.type.lower()] = link.url
        return links

    def is_visible_to_user(self, user: User | AbstractUser) -> bool:
        """Check if incident is visible to the given user"""
        if not self.is_private:
            return True

        # Superusers can see all incidents
        if user.is_superuser:
            return True

        # Check if user is involved
        if user in [self.captain, self.reporter]:
            return True

        if self.participants.filter(id=user.id).exists():
            return True

        return False

    def clean(self) -> None:
        """Custom validation"""

        if not self.title or not self.title.strip():
            raise ValidationError({"title": "Title cannot be empty"})

        if not self.severity:
            raise ValidationError({"severity": "Severity must be set"})

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Override save to run validation and assign gapless ID"""
        with transaction.atomic():
            if self._state.adding and self.id is None:
                self.id = get_next_incident_id()
            self.full_clean()
            super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.incident_number}: {self.title}"


class ExternalLink(models.Model):
    """
    Links to external resources related to an incident.

    One link per type per incident (e.g., one Slack channel link).
    """

    incident = models.ForeignKey(
        "Incident", on_delete=models.CASCADE, related_name="external_links"
    )
    type = models.CharField(max_length=20, choices=ExternalLinkType.choices)
    url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("incident", "type")]

    def __str__(self) -> str:
        return f"{self.incident.incident_number} - {self.type}"


def filter_visible_to_user(
    queryset: QuerySet[Incident], user: User | AbstractUser
) -> QuerySet[Incident]:
    """
    Filter incidents queryset to only those visible to user.

    Args:
        queryset: Incident queryset to filter
        user: User to check visibility for

    Returns:
        Filtered queryset
    """
    # Anonymous users see no incidents. IAP should prevent this, but just in case.
    if not user.is_authenticated:
        return queryset.none()

    # Superusers see everything
    if user.is_superuser:
        return queryset

    return queryset.filter(
        Q(is_private=False) | Q(captain=user) | Q(reporter=user) | Q(participants=user)
    ).distinct()
