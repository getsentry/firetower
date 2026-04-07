import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

EVENTS_API_URL = "https://events.pagerduty.com/v2/enqueue"
REST_API_URL = "https://api.pagerduty.com"


class PagerDutyService:
    def __init__(self) -> None:
        pd_config = settings.PAGERDUTY
        if not pd_config:
            raise ValueError("PagerDuty is not configured")

        self.api_token = pd_config["API_TOKEN"]

    def trigger_incident(
        self, summary: str, dedup_key: str, integration_key: str
    ) -> bool:
        payload = {
            "routing_key": integration_key,
            "event_action": "trigger",
            "dedup_key": dedup_key,
            "payload": {
                "summary": summary,
                "severity": "critical",
                "source": "firetower",
            },
        }

        try:
            resp = requests.post(EVENTS_API_URL, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info(
                "Triggered PagerDuty incident",
                extra={"dedup_key": dedup_key},
            )
            return True
        except requests.RequestException:
            logger.exception(
                "Failed to trigger PagerDuty incident",
                extra={"dedup_key": dedup_key},
            )
            return False

    def get_oncall_users(self, escalation_policy_id: str) -> list[dict]:
        headers = {
            "Authorization": f"Token token={self.api_token}",
            "Content-Type": "application/json",
        }

        url = f"{REST_API_URL}/oncalls"
        params = {"escalation_policy_ids[]": escalation_policy_id}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            results = []
            for oncall in resp.json().get("oncalls", []):
                user = oncall.get("user", {})
                email = user.get("email")
                if email:
                    results.append(
                        {
                            "email": email,
                            "escalation_level": oncall.get("escalation_level"),
                        }
                    )
            return results
        except requests.RequestException:
            logger.exception(
                "Failed to fetch oncall users from PagerDuty",
                extra={"escalation_policy_id": escalation_policy_id},
            )
            return []
