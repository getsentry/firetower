"""Hop 2: firetower data access via the in-repo ``firetower_sdk``.

A single ``FiretowerClient`` (the MCP server's service identity) authenticates to
the IAP-protected firetower API. Because that service account is captain/reporter
of nothing, firetower's ``filter_visible_to_user`` returns only non-private
incidents, so the privacy guarantee falls out for free.

Only methods exposed by ``firetower_sdk`` are used — no raw endpoint access.
"""

from functools import lru_cache

from firetower_sdk.client import FiretowerClient

from firetower.mcp_server.config import MCPConfig


@lru_cache(maxsize=1)
def get_client() -> FiretowerClient:
    config = MCPConfig.from_env()
    return FiretowerClient(
        service_account=config.service_account,
        base_url=config.firetower_url,
    )
