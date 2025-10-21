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


class ExternalProfileType(models.TextChoices):
    SLACK = "SLACK", "Slack"
    PAGERDUTY = "PAGERDUTY", "PagerDuty"
    LINEAR = "LINEAR", "Linear"
    DATADOG = "DATADOG", "Datadog"
