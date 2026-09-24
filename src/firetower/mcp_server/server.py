"""Firetower MCP server assembly.

Hop 1 (client -> server): Google OAuth gated to the Sentry Workspace via
``SentryGoogleProvider``. Hop 2 (server -> firetower): the tools read through
``firetower_sdk`` as a single service identity (non-private incidents only).

Deployed as its own Cloud Run service over Streamable HTTP.
"""

import logging

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from firetower.mcp_server.auth import GOOGLE_GROUPS_READ_SCOPE, SentryGoogleProvider
from firetower.mcp_server.branding import FIRETOWER_ICON, FIRETOWER_ICON_SVG
from firetower.mcp_server.config import MCPConfig
from firetower.mcp_server.tools import register_tools

logger = logging.getLogger(__name__)


async def health(_request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


async def favicon(_request: Request) -> Response:
    return Response(
        FIRETOWER_ICON_SVG,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


def create_mcp(config: MCPConfig | None = None) -> FastMCP:
    config = config or MCPConfig.from_env()
    provider_kwargs: dict = {
        "client_id": config.google_client_id,
        "client_secret": config.google_client_secret,
        "base_url": config.base_url,
        "jwt_signing_key": config.jwt_signing_key,
        "required_scopes": ["openid", "email", GOOGLE_GROUPS_READ_SCOPE],
        "enable_cimd": False,
        "require_authorization_consent": True,  # confused-deputy mitigation
        # Native MCP clients use loopback callbacks, while hosted callbacks must
        # be explicitly trusted. Required so arbitrary redirect URIs never fall open.
        "allowed_client_redirect_uris": list(config.allowed_redirect_uris),
    }
    auth = SentryGoogleProvider(**provider_kwargs)
    mcp = FastMCP(name="Firetower", icons=[FIRETOWER_ICON], auth=auth)
    mcp.custom_route("/health", methods=["GET"], include_in_schema=False)(health)
    mcp.custom_route("/favicon.ico", methods=["GET"], include_in_schema=False)(favicon)
    register_tools(mcp)
    return mcp


def main() -> None:
    config = MCPConfig.from_env()
    logger.info("Starting Firetower MCP server on %s:%s", config.host, config.port)
    create_mcp(config).run(transport="http", host=config.host, port=config.port)


if __name__ == "__main__":
    main()
