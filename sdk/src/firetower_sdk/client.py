import logging
from typing import Any

import requests

from firetower_sdk.auth import JWTInterface, JwtAuth
from firetower_sdk.enums import IncidentSeverity, IncidentStatus, ServiceTier
from firetower_sdk.exceptions import FiretowerError
from firetower_sdk.utils import get_base_url

logger = logging.getLogger(__name__)


class FiretowerClient:
    """Client for interacting with the Firetower incident management API."""

    def __init__(
        self,
        service_account: str,
        base_url: str | None = None,
    ):
        if base_url is None:
            base_url = get_base_url()
        self.base_url = base_url.rstrip("/")
        jwt_interface = JWTInterface(service_account)
        self.session = requests.Session()
        self.session.auth = JwtAuth(jwt_interface)

    def _request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        logger.info(f"Firetower API {method} {url}")

        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.HTTPError as e:
            error_msg = f"Firetower API error ({e.response.status_code}): {e.response.text}"
            logger.error(error_msg)
            raise FiretowerError(error_msg, status_code=e.response.status_code) from e
        except requests.exceptions.RequestException as e:
            error_msg = f"Firetower API request failed: {e}"
            logger.error(error_msg)
            raise FiretowerError(error_msg) from e

    def create_incident(
        self,
        title: str,
        severity: str | IncidentSeverity,
        captain_email: str,
        reporter_email: str,
        description: str | None = None,
        impact_summary: str | None = None,
        status: str | IncidentStatus = IncidentStatus.ACTIVE,
        is_private: bool = False,
    ) -> str:
        """
        Create a new incident in Firetower.

        Returns the incident ID (e.g., "INC-2000").
        """
        payload: dict[str, Any] = {
            "title": title,
            "severity": severity,
            "captain": captain_email,
            "reporter": reporter_email,
            "status": status,
            "is_private": is_private,
        }

        if description is not None:
            payload["description"] = description
        if impact_summary is not None:
            payload["impact_summary"] = impact_summary

        response = self._request("POST", "/api/incidents/", data=payload)
        incident_id = response["id"]
        logger.info(f"Created Firetower incident {incident_id}")
        return incident_id

    def get_incident(self, incident_id: str) -> dict[str, Any]:
        """Get an incident by ID."""
        return self._request("GET", f"/api/incidents/{incident_id}/")

    def list_incidents(
        self,
        statuses: list[str | IncidentStatus] | None = None,
        severities: list[str | IncidentSeverity] | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
        service_tiers: list[str | ServiceTier] | None = None,
        affected_service: list[str] | None = None,
        root_cause: list[str] | None = None,
        impact_type: list[str] | None = None,
        affected_region: list[str] | None = None,
        page: int = 1,
    ) -> dict[str, Any]:
        """List incidents with optional filtering.

        Args:
            statuses: Filter by status (e.g., ["Active", "Mitigated"])
            severities: Filter by severity (e.g., ["P0", "P1"])
            created_after: Filter incidents created after this date (ISO 8601 format)
            created_before: Filter incidents created before this date (ISO 8601 format)
            service_tiers: Filter by service tier (e.g., ["T0", "T1"])
            affected_service: Filter by affected service tags (OR within type)
            root_cause: Filter by root cause tags (OR within type)
            impact_type: Filter by impact type tags (OR within type)
            affected_region: Filter by affected region tags (OR within type)
            page: Page number for pagination
        """
        params: dict[str, Any] = {"page": page}
        if statuses:
            params["status"] = statuses
        if severities:
            params["severity"] = severities
        if created_after:
            params["created_after"] = created_after
        if created_before:
            params["created_before"] = created_before
        if service_tiers:
            params["service_tier"] = service_tiers
        if affected_service:
            params["affected_service"] = affected_service
        if root_cause:
            params["root_cause"] = root_cause
        if impact_type:
            params["impact_type"] = impact_type
        if affected_region:
            params["affected_region"] = affected_region
        return self._request("GET", "/api/incidents/", params=params)

    def update_incident(self, incident_id: str, **fields: Any) -> dict[str, Any]:
        """Update an incident with arbitrary fields."""
        return self._request("PATCH", f"/api/incidents/{incident_id}/", data=fields)

    def update_status(self, incident_id: str, status: str | IncidentStatus) -> dict[str, Any]:
        """Update incident status."""
        return self.update_incident(incident_id, status=status)

    def update_severity(self, incident_id: str, severity: str | IncidentSeverity) -> dict[str, Any]:
        """Update incident severity."""
        return self.update_incident(incident_id, severity=severity)

    def update_captain(self, incident_id: str, captain_email: str) -> dict[str, Any]:
        """Update incident captain."""
        return self.update_incident(incident_id, captain=captain_email)

    def update_external_link(
        self, incident_id: str, link_type: str, url: str | None
    ) -> dict[str, Any]:
        """Update a single external link on an incident. Pass None to remove the link."""
        return self.update_incident(incident_id, external_links={link_type: url})

    def append_description(self, incident_id: str, text: str) -> dict[str, Any]:
        """Append text to an incident's description."""
        incident = self.get_incident(incident_id)
        current_description = incident.get("description") or ""
        new_description = f"{current_description}\n\n{text}".strip()
        return self.update_incident(incident_id, description=new_description)
