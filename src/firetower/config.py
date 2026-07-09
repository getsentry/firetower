"""
Configuration file loader for Firetower.

Loads configuration values from a TOML file and validates that all required keys are present.
"""

from dataclasses import field
from pathlib import Path
from typing import Any

from serde import deserialize, from_dict
from serde.toml import from_toml


@deserialize
class PostgresConfig:
    db: str
    host: str
    user: str
    password: str
    # Additional passwords tried (in order) only when `password` fails
    # authentication. Used to bridge the race window during a password
    # rotation, when the server and app may briefly disagree on the password.
    fallback_passwords: list[str] = field(default_factory=list)


@deserialize
class EscalationPolicy:
    id: str
    integration_key: str | None = None


@deserialize
class PagerDutyConfig:
    api_token: str
    escalation_policies: dict[str, EscalationPolicy]


@deserialize
class SlackConfig:
    bot_token: str
    team_id: str
    participant_sync_throttle_seconds: int
    app_token: str
    incident_feed_channel_id: str = ""
    always_invited_ids: list[str] = field(default_factory=list)
    incident_guide_message: str = ""
    slash_command: str = "/inc"


@deserialize
class GenAIConfig:
    model: str = "gemini-2.5-flash"


@deserialize
class NotionConfig:
    integration_token: str
    database_id: str
    template_markdown: str = ""
    troubleshooting_database_id: str = ""
    troubleshooting_template_markdown: str = ""


@deserialize
class StatuspageConfig:
    api_key: str
    page_id: str
    url: str
    initial_reminder_delay_minutes: int | None = None
    followup_reminder_delay_minutes: int | None = None
    warning_buffer_minutes: int = 0


@deserialize
class LinearConfig:
    client_id: str = ""
    client_secret: str = ""
    action_item_sync_throttle_seconds: int = 300
    team_id: str = ""
    project_id: str = ""
    sync_identifiers: bool = False
    api_key: str = ""
    action_item_slo_days_high_priority: int = 14
    action_item_slo_days_medium_priority: int = 30
    action_item_nag_comment_high_priority: str = (
        "{% if days_past_due > 0 %}This action item is **{{ days_past_due }} "
        "day{% if days_past_due != 1 %}s{% endif %} past due**. {% endif %}"
        "The SLO for completing P0/P1 incident action items is {{ slo_days }} "
        "days from incident creation. Please prioritize this work or close "
        "out the issue if it is no longer relevant."
    )
    action_item_nag_comment_medium_priority: str = (
        "{% if days_past_due > 0 %}This action item is **{{ days_past_due }} "
        "day{% if days_past_due != 1 %}s{% endif %} past due**. {% endif %}"
        "The SLO for completing P2 incident action items is {{ slo_days }} "
        "days from incident creation. Please prioritize this work or close "
        "out the issue if it is no longer relevant."
    )
    parent_status_comment_completed: str = (
        "Firetower set this issue to **Completed**. "
        "Incident {{ incident.incident_number }} is {{ incident.status }} "
        "and {% if total_action_items == 0 %}there are no action items."
        "{% else %}all {{ total_action_items }} action "
        "item{% if total_action_items != 1 %}s{% endif %} are complete.{% endif %}"
    )
    parent_status_comment_started: str = (
        "Firetower set this issue to **Started**. "
        "Incident {{ incident.incident_number }} is {{ incident.status }}. "
        "{% if total_action_items == 0 %}There are no action items."
        "{% else %}{{ completed_action_items }} of {{ total_action_items }} action "
        "item{% if total_action_items != 1 %}s{% endif %} complete.{% endif %}"
    )


@deserialize
class AuthConfig:
    iap_enabled: bool
    iap_audience: str | None


@deserialize
class ConfigFile:
    """
    Load string configuration values from a TOML file.
    """

    postgres: PostgresConfig
    slack: SlackConfig
    linear: LinearConfig | None
    auth: AuthConfig
    pagerduty: PagerDutyConfig | None
    statuspage: StatuspageConfig | None

    project_key: str
    firetower_base_url: str
    django_secret_key: str
    salt_key: str
    sentry_dsn: str
    service_registry_url: str | None = None
    # When non-empty, `salt_keys` overrides `salt_key`. Used for key rotation:
    # values are encrypted with the first key and can be decrypted with any.
    salt_keys: list[str] = field(default_factory=list)
    notion: NotionConfig | None = None
    genai: GenAIConfig | None = None
    log_level: str = "INFO"
    hooks_enabled: bool = (
        False  # TODO: remove after hooks migration is complete and always enable
    )
    region_grouping: list[list[str]] = field(default_factory=list)

    @classmethod
    def from_file(cls, file_path: str | Path) -> "ConfigFile":
        """
        Load configuration from a TOML file.

        Args:
            file_path: Path to the TOML configuration file.

        Returns:
            ConfigFile instance with loaded configuration.
        """
        with open(file_path) as f:
            data: ConfigFile = from_toml(ConfigFile, f.read())
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConfigFile":
        """
        Load configuration from a dictionary.

        Args:
            data: Dictionary containing configuration key-value pairs.

        Returns:
            ConfigFile instance with loaded configuration.
        """
        return from_dict(ConfigFile, data)


class DummyConfigFile(ConfigFile):
    """
    A dummy configuration file for use when running collectstatic.
    """

    def __init__(self) -> None:
        self.postgres = PostgresConfig(
            db="firetower",
            host="localhost",
            user="postgres",
            password="dummy_dev_password",
            fallback_passwords=[],
        )
        self.slack = SlackConfig(
            bot_token="",
            team_id="",
            participant_sync_throttle_seconds=0,
            app_token="",
            incident_feed_channel_id="",
            always_invited_ids=[],
            incident_guide_message="",
        )
        self.auth = AuthConfig(
            iap_enabled=False,
            iap_audience="",
        )
        self.linear = None
        self.notion = None
        self.genai = None
        self.pagerduty = None
        self.statuspage = None
        self.project_key = ""
        self.firetower_base_url = ""
        self.django_secret_key = "dummy_value_DO_NOT_USE"
        self.salt_key = ""
        self.salt_keys = []
        self.sentry_dsn = ""
        self.service_registry_url = None
        self.region_grouping: list[list[str]] = []
        self.log_level = "INFO"
        self.hooks_enabled = False
