"""Environment-driven configuration for the Firetower MCP server.

The MCP server runs as its own Cloud Run service and talks to firetower over
HTTP via ``firetower_sdk``, so it does not need Django settings or the database.
All configuration comes from the environment to keep deployment self-contained.

See ``.env.mcp.example`` for the full list of variables.
"""

import os
from dataclasses import dataclass

WORKSPACE_DOMAIN = "sentry.io"


class ConfigError(RuntimeError):
    """Raised when required MCP server configuration is missing."""


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class MCPConfig:
    """Resolved configuration for the MCP server."""

    google_client_id: str
    google_client_secret: str
    base_url: str
    service_account: str
    firetower_url: str | None
    jwt_signing_key: str | None
    allowed_redirect_uris: tuple[str, ...]
    host: str
    port: int

    @classmethod
    def from_env(cls) -> "MCPConfig":
        raw_redirects = _require("MCP_ALLOWED_REDIRECT_URIS")
        allowed_redirect_uris = tuple(
            u.strip() for u in raw_redirects.split(",") if u.strip()
        )
        if not allowed_redirect_uris:
            # An empty/whitespace value would let fastmcp fall open to ANY
            # redirect URI, so refuse to start for this confidential-data service.
            raise ConfigError(
                "MCP_ALLOWED_REDIRECT_URIS must list at least one redirect URI."
            )
        return cls(
            google_client_id=_require("MCP_GOOGLE_CLIENT_ID"),
            google_client_secret=_require("MCP_GOOGLE_CLIENT_SECRET"),
            base_url=_require("MCP_BASE_URL"),
            service_account=_require("FIRETOWER_SERVICE_ACCOUNT"),
            firetower_url=os.environ.get("FIRETOWER_URL"),
            jwt_signing_key=os.environ.get("MCP_JWT_SIGNING_KEY"),
            allowed_redirect_uris=allowed_redirect_uris,
            host=os.environ.get("MCP_HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "8080")),
        )
