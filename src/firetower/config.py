"""
Configuration file loader for Firetower.

Loads configuration values from a TOML file and validates that all required keys are present.
"""

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
    auth: AuthConfig

    project_key: str
    django_secret_key: str
    sentry_dsn: str

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
