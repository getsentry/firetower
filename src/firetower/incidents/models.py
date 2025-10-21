from django.db import models


class IncidentStatus(models.TextChoices):
    ACTIVE = "Active", "Active"
    MITIGATED = "Mitigated", "Mitigated"
    POSTMORTEM = "Postmortem", "Postmortem"
    ACTIONS_PENDING = "Actions Pending", "Actions Pending"
    DONE = "Done", "Done"


class IncidentSeverity(models.TextChoices):
    P0 = "P0", "P0"
    P1 = "P1", "P1"
    P2 = "P2", "P2"
    P3 = "P3", "P3"
    P4 = "P4", "P4"


class TagType(models.TextChoices):
    AFFECTED_AREA = "AFFECTED_AREA", "Affected Area"
    ROOT_CAUSE = "ROOT_CAUSE", "Root Cause"


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

    tag_type determines if this is an affected area or root cause.
    Same name can exist for both types (e.g., "Database").
    """

    name = models.CharField(max_length=100)
    tag_type = models.CharField(max_length=20, choices=TagType.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("name", "tag_type")]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_tag_type_display()})"


class Incident(models.Model):
    """
    Core incident model.

    The id field is the numeric identifier (2000, 2001, etc.) and is exposed
    as "INC-{id}" via the incident_number property.
    """

    # Primary key - numeric ID (2000, 2001, etc.)
    id = models.AutoField(primary_key=True)

    # Core fields
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    impact = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)

    # Status and severity
    status = models.CharField(
        max_length=20, choices=IncidentStatus.choices, default=IncidentStatus.ACTIVE
    )
    severity = models.CharField(max_length=2, choices=IncidentSeverity.choices)

    # Privacy
    is_private = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
    affected_area_tags = models.ManyToManyField(
        "Tag",
        blank=True,
        related_name="incidents_by_affected_area",
        limit_choices_to={"tag_type": "AFFECTED_AREA"},
    )
    root_cause_tags = models.ManyToManyField(
        "Tag",
        blank=True,
        related_name="incidents_by_root_cause",
        limit_choices_to={"tag_type": "ROOT_CAUSE"},
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["severity", "-created_at"]),
        ]

    @property
    def incident_number(self):
        """Return formatted incident number (e.g., 'INC-2000')"""
        from django.conf import settings

        return f"{settings.PROJECT_KEY}-{self.id}"

    @property
    def affected_areas(self):
        """Return list of affected area names"""
        return list(self.affected_area_tags.values_list("name", flat=True))

    @property
    def root_causes(self):
        """Return list of root cause names"""
        return list(self.root_cause_tags.values_list("name", flat=True))

    @property
    def external_links_dict(self):
        """Return external links as dict with lowercase keys"""
        links = {link_type.lower(): None for link_type in ExternalLinkType.values}
        for link in self.external_links.all():
            links[link.link_type.lower()] = link.url
        return links

    def is_visible_to_user(self, user):
        """Check if incident is visible to the given user"""
        if not self.is_private:
            return True

        # Admins can see all incidents
        if hasattr(user, "userprofile") and user.userprofile.is_admin:
            return True

        # Check if user is involved
        if user in [self.captain, self.reporter]:
            return True

        if self.participants.filter(id=user.id).exists():
            return True

        return False

    def clean(self):
        """Custom validation"""
        from django.core.exceptions import ValidationError

        if not self.title or not self.title.strip():
            raise ValidationError({"title": "Title cannot be empty"})

        if not self.severity:
            raise ValidationError({"severity": "Severity must be set"})

    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.incident_number}: {self.title}"


class ExternalLink(models.Model):
    """
    Links to external resources related to an incident.

    One link per type per incident (e.g., one Slack channel link).
    """

    incident = models.ForeignKey(
        "Incident", on_delete=models.CASCADE, related_name="external_links"
    )
    link_type = models.CharField(max_length=20, choices=ExternalLinkType.choices)
    url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("incident", "link_type")]

    def __str__(self):
        return f"{self.incident.incident_number} - {self.link_type}"


def filter_visible_to_user(queryset, user):
    """
    Filter incidents queryset to only those visible to user.

    Args:
        queryset: Incident queryset to filter
        user: User to check visibility for

    Returns:
        Filtered queryset
    """
    if hasattr(user, "userprofile") and user.userprofile.is_admin:
        return queryset

    from django.db.models import Q

    return queryset.filter(
        Q(is_private=False) | Q(captain=user) | Q(reporter=user) | Q(participants=user)
    ).distinct()
