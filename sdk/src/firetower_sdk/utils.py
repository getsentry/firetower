import re

FIRETOWER_ID_CUTOFF = 2000


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


def get_firetower_url(incident_id: str, base_url: str = "https://firetower.getsentry.net") -> str:
    """Get the Firetower UI URL for an incident."""
    return f"{base_url.rstrip('/')}/{incident_id}"
