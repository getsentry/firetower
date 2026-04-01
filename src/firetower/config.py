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


@deserialize
class DatadogConfig:
    api_key: str
    app_key: str


@deserialize
class JIRAConfig:
    domain: str
    account: str
    api_key: str
    severity_field: str


@deserialize
class SlackConfig:
    bot_token: str
    team_id: str
    participant_sync_throttle_seconds: int
    app_token: str
    incident_feed_channel_id: str = ""
    always_invited_ids: list[str] = field(default_factory=list)
    incident_guide_message: str = ""


@deserialize
class LinearConfig:
    api_key: str
    action_item_sync_throttle_seconds: int


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
    datadog: DatadogConfig | None
    jira: JIRAConfig
    slack: SlackConfig
    linear: LinearConfig | None
    auth: AuthConfig

    project_key: str
    firetower_base_url: str
    django_secret_key: str
    sentry_dsn: str
    firetower_base_url: str
    hooks_enabled: bool = (
        False  # TODO: remove after hooks migration is complete and always enable
    )
    pinned_regions: list[str] = field(default_factory=list)

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
        )
        self.jira = JIRAConfig(
            domain="",
            account="",
            api_key="",
            severity_field="",
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
        self.datadog = None
        self.project_key = ""
        self.firetower_base_url = ""
        self.django_secret_key = ""
        self.sentry_dsn = ""
        self.pinned_regions: list[str] = []
        self.firetower_base_url = ""
        self.hooks_enabled = False
