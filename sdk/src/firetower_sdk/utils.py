import os
import re

FIRETOWER_ID_CUTOFF = 2000

DEFAULT_BASE_URL = "https://firetower.getsentry.net"


def get_base_url() -> str:
    """Get the Firetower base URL from environment variable or default."""
    return os.environ.get("FIRETOWER_URL", DEFAULT_BASE_URL)


def is_firetower_incident_id(incident_id: str | int) -> bool:
    """
    Determine if an incident ID belongs to Firetower based on its numeric portion.

    Firetower incidents have IDs >= 2000 (e.g., INC-2000, INC-2001).
    Jira incidents have IDs < 2000 (e.g., INC-1, INC-1999).

    Args:
        incident_id: Either a numeric ID or a string like "INC-2000"

    Returns:
        True if the incident belongs to Firetower, False otherwise.

    Raises:
        ValueError: If the incident ID format is invalid.
    """
    if isinstance(incident_id, int):
        return incident_id >= FIRETOWER_ID_CUTOFF

    match = re.search(r"-(\d+)$", incident_id)
    if not match:
        raise ValueError(f"Invalid incident ID format: {incident_id}")

    incident_num = int(match.group(1))
    return incident_num >= FIRETOWER_ID_CUTOFF


def get_firetower_url(incident_id: str, base_url: str | None = None) -> str:
    """Get the Firetower UI URL for an incident."""
    if base_url is None:
        base_url = get_base_url()
    return f"{base_url.rstrip('/')}/{incident_id}"
