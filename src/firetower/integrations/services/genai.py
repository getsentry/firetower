import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

_METADATA_BASE = "http://metadata.google.internal/computeMetadata/v1"
_METADATA_HEADERS = {"Metadata-Flavor": "Google"}
_METADATA_TIMEOUT = 1.0
_DEFAULT_LOCATION = "us-central1"

_TIMELINE_PROMPT = """\
You are an expert incident analyst. Based on the following Slack channel messages \
from an incident response, create a concise timeline of key events.

{context}Slack Channel Messages:
{messages_text}

Please generate a timeline that:
1. Identifies key events and milestones (started, detected, investigation steps, \
root cause identification, mitigation, resolution)
2. Uses bullet points with timestamps in chronological order
3. Summarizes the most important actions and decisions
4. Excludes casual conversation and focuses on incident-relevant information
5. Groups related activities when appropriate
6. Highlights any identified root cause or contributing factors

Keep the timeline concise but comprehensive, focusing on the most important events.

Your response MUST follow this exact format:

## Timeline
- [YYYY-MM-DD HH:MM UTC] - Description of event
- [YYYY-MM-DD HH:MM UTC] - Description of event
(continue for all key events)

## Key Timestamps
- Started: [YYYY-MM-DD HH:MM UTC]
- Detected: [YYYY-MM-DD HH:MM UTC]
- Understanding: [YYYY-MM-DD HH:MM UTC]
- Mitigation: [YYYY-MM-DD HH:MM UTC]
- Resolution: [YYYY-MM-DD HH:MM UTC]

If a timestamp is unknown or not applicable, use "N/A" instead of a timestamp.\
"""


def _detect_location() -> str:
    """Query the GCP metadata server for the Cloud Run region.

    Falls back to us-central1 when not running on GCP (e.g. local dev).
    The metadata server returns a path like 'projects/123/regions/us-central1'.
    """
    try:
        resp = requests.get(
            f"{_METADATA_BASE}/instance/region",
            headers=_METADATA_HEADERS,
            timeout=_METADATA_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.text.strip().split("/")[-1]
    except Exception:
        logger.debug(
            "Could not detect GCP region from metadata server; using %s",
            _DEFAULT_LOCATION,
        )
        return _DEFAULT_LOCATION


class GenAIService:
    @classmethod
    def is_configured(cls) -> bool:
        from django.conf import settings  # noqa: PLC0415

        return bool(getattr(settings, "GENAI", None))

    @classmethod
    def from_settings(cls) -> "GenAIService | None":
        from django.conf import settings  # noqa: PLC0415

        config = getattr(settings, "GENAI", None)
        if not config:
            return None
        return cls(model=config.get("MODEL", "gemini-2.5-flash"))

    def __init__(self, model: str = "gemini-2.5-flash") -> None:
        from google import genai  # noqa: PLC0415

        # project=None lets the SDK infer from GOOGLE_CLOUD_PROJECT env var or ADC.
        # location is read from the GCP metadata server so no explicit config is needed.
        self._client = genai.Client(
            vertexai=True,
            project=None,
            location=_detect_location(),
        )
        self._model = model

    def generate_timeline(
        self,
        messages: list[dict[str, Any]],
        incident_summary: str | None = None,
    ) -> str | None:
        if not messages:
            logger.warning("No messages provided for timeline generation")
            return None

        try:
            formatted = []
            for msg in messages:
                ts = msg["date_time"].strftime("%Y-%m-%d %H:%M:%S UTC")
                author = msg.get("author") or "Unknown"
                text = msg.get("text", "")
                formatted.append(f"[{ts}] {author}: {text}")

                for reply in msg.get("replies", [])[1:]:
                    rts = reply["date_time"].strftime("%Y-%m-%d %H:%M:%S UTC")
                    rauthor = reply.get("author") or "Unknown"
                    rtext = reply.get("text", "")
                    formatted.append(f"  -> [{rts}] {rauthor}: {rtext}")

            context = (
                f"Incident Summary: {incident_summary}\n\n" if incident_summary else ""
            )
            prompt = _TIMELINE_PROMPT.format(
                context=context,
                messages_text="\n".join(formatted),
            )

            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
            )

            if response and response.text:
                logger.info("Successfully generated timeline using Gemini")
                return response.text

            logger.warning("Gemini returned empty response for timeline generation")
            return None

        except Exception:
            logger.exception("Failed to generate timeline with Gemini")
            return None
