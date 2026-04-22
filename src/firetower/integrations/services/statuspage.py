import logging
from collections import defaultdict
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

STATUSPAGE_API_BASE = "https://api.statuspage.io/v1"

STATUS_OPTIONS = [
    ("investigating", "Investigating"),
    ("identified", "Identified"),
    ("monitoring", "Monitoring"),
    ("resolved", "Resolved"),
]

IMPACT_OPTIONS = [
    ("critical", "Critical"),
    ("major", "Major"),
    ("minor", "Minor"),
    ("none", "None"),
]

COMPONENT_STATUS_OPTIONS = [
    ("operational", "Operational"),
    ("degraded_performance", "Degraded Performance"),
    ("partial_outage", "Partial Outage"),
    ("major_outage", "Major Outage"),
]

DEFAULT_MESSAGES = {
    "investigating": "We are currently investigating this issue.",
    "identified": "The issue has been identified and a fix is being implemented.",
    "monitoring": "A fix has been implemented and we are monitoring the results.",
    "resolved": "This incident has been resolved.",
}

SEVERITY_TO_IMPACT = {
    "P0": "critical",
    "P1": "major",
    "P2": "minor",
    "P3": "minor",
    "P4": "none",
}


class StatuspageService:
    def __init__(self) -> None:
        statuspage_config = settings.STATUSPAGE
        if not statuspage_config:
            self.api_key = ""
            self.page_id = ""
            self.base_url = ""
            self.configured = False
            logger.warning("StatuspageService initialized without configuration")
            return

        self.api_key = statuspage_config["API_KEY"]
        self.page_id = statuspage_config["PAGE_ID"]
        self.base_url = statuspage_config["URL"]
        self.configured = bool(self.api_key and self.page_id)

        if not self.configured:
            logger.warning("StatuspageService missing API key or page ID")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"OAuth {self.api_key}",
            "Content-Type": "application/json",
        }

    def _api_url(self, path: str) -> str:
        return f"{STATUSPAGE_API_BASE}/pages/{self.page_id}/{path}"

    def get_components(
        self,
    ) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        response = requests.get(
            self._api_url("components"),
            headers=self._headers(),
        )
        response.raise_for_status()
        components = response.json()

        children_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for component in components:
            group_id = component.get("group_id")
            if group_id:
                children_map[group_id].append(component)

        top_level = [c for c in components if not c.get("group_id")]
        return top_level, children_map

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        response = requests.get(
            self._api_url(f"incidents/{incident_id}"),
            headers=self._headers(),
        )
        if response.status_code == 200:
            return response.json()
        logger.error(
            "Failed to fetch statuspage incident %s: %s",
            incident_id,
            response.status_code,
        )
        return None

    def create_incident(
        self,
        title: str,
        status: str,
        message: str,
        impact: str = "major",
        components: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "incident": {
                "name": title,
                "status": status,
                "body": message,
                "impact": impact,
                "deliver_notifications": True,
            }
        }
        if components:
            payload["incident"]["components"] = components

        response = requests.post(
            self._api_url("incidents"),
            json=payload,
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def update_incident(
        self,
        incident_id: str,
        status: str | None = None,
        message: str | None = None,
        components: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        incident_data: dict[str, Any] = {"deliver_notifications": True}
        if status:
            incident_data["status"] = status
        if message:
            incident_data["body"] = message
        if components:
            incident_data["components"] = components

        payload = {"incident": incident_data}

        response = requests.patch(
            self._api_url(f"incidents/{incident_id}"),
            json=payload,
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def get_incident_url(self, incident_id: str) -> str:
        return f"{self.base_url}incidents/{incident_id}"

    def extract_incident_id_from_url(self, url: str) -> str | None:
        if not url:
            return None
        parts = url.rstrip("/").split("/")
        return parts[-1] if parts else None
