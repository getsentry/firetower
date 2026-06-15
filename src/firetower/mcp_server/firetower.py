"""Hop 2: firetower data access via the in-repo ``firetower_sdk``.

A single ``FiretowerClient`` (the MCP server's service identity) authenticates to
the IAP-protected firetower API. Because that service account is captain/reporter
of nothing, firetower's ``filter_visible_to_user`` returns only non-private
incidents, so the privacy guarantee falls out for free.

Only methods exposed by ``firetower_sdk`` are used — no raw endpoint access.

Concurrency: the SDK uses a single shared blocking ``requests.Session`` with a
30s timeout. This is safe on FastMCP's async server because FastMCP dispatches
sync ``@mcp.tool`` functions via ``anyio.to_thread.run_sync``
(``fastmcp/tools/function_tool.py`` -> ``call_sync_fn_in_threadpool``), so a slow
SDK call runs on a worker thread and does not block the event loop. ``requests``
sessions are thread-safe for this usage pattern.
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
