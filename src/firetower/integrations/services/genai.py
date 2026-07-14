import logging
import re
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

_TIMELINE_PROMPT_PREFIX = """\
You are an expert incident analyst. Based on the following Slack channel messages \
from an incident response, create a concise timeline of key events.

"""

_TIMELINE_PROMPT_SUFFIX = """

Please generate a timeline that:
1. Identifies key events and milestones (started, detected, investigation steps, \
root cause identification, mitigation, resolution)
2. Uses bullet points with timestamps in chronological order
3. Summarizes the most important actions and decisions
4. Excludes casual conversation and focuses on incident-relevant information
5. Groups related activities when appropriate
6. Highlights any identified root cause or contributing factors
7. Itemize any thing that has been called out as an "action item"

Keep the timeline concise but comprehensive, focusing on the most important events.

Your response MUST follow this exact format:

## Timeline
- [YYYY-MM-DD HH:MM UTC] - Description of event
- [YYYY-MM-DD HH:MM UTC] - Description of event
(continue for all key events)

## Action Items
- <action items here>

## Key Timestamps
- Started: [YYYY-MM-DD HH:MM UTC]
- Detected: [YYYY-MM-DD HH:MM UTC]
- Analyzed: [YYYY-MM-DD HH:MM UTC]
- Mitigation: [YYYY-MM-DD HH:MM UTC]
- Resolution: [YYYY-MM-DD HH:MM UTC]

If a timestamp is unknown or not applicable, use "N/A" instead of a timestamp."""


_KEY_TIMESTAMPS_LABEL_MAP = {
    "started": "time_started",
    "detected": "time_detected",
    "analyzed": "time_analyzed",
    "mitigation": "time_mitigated",
    "resolution": "time_recovered",
}

_KEY_TS_RE = re.compile(
    r"-\s*(\w+):\s*\[?(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?\s*UTC)\]?",
    re.IGNORECASE,
)


def parse_key_timestamps(timeline_md: str) -> dict[str, datetime]:
    """Extract Key Timestamps from the AI-generated timeline markdown.

    Returns a dict mapping Incident model field names to parsed datetimes.
    Only includes entries where the AI provided a real timestamp (not N/A).
    """
    section_match = re.search(
        r"## Key Timestamps\s*\n((?:- .+\n?)+)", timeline_md, re.IGNORECASE
    )
    if not section_match:
        return {}

    results: dict[str, datetime] = {}
    for match in _KEY_TS_RE.finditer(section_match.group(1)):
        label = match.group(1).lower()
        field = _KEY_TIMESTAMPS_LABEL_MAP.get(label)
        if not field:
            continue
        raw_ts = " ".join(match.group(2).replace("UTC", " UTC").split())
        for fmt in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d %H:%M UTC"):
            try:
                results[field] = datetime.strptime(raw_ts, fmt).replace(tzinfo=UTC)
                break
            except ValueError:
                continue
    return results


class GenAIService:
    @classmethod
    def from_settings(cls) -> "GenAIService | None":
        from django.conf import settings  # noqa: PLC0415

        config = getattr(settings, "GENAI", None)
        if not config:
            return None
        api_key = config.get("API_KEY")
        if not api_key:
            return None
        return cls(
            api_key=api_key,
            model=config.get("MODEL", "google/gemini-2.5-flash"),
        )

    def __init__(
        self,
        api_key: str,
        model: str = "google/gemini-2.5-flash",
    ) -> None:
        from openrouter import OpenRouter  # noqa: PLC0415

        # OpenRouter is the company-wide AI gateway; the SDK defaults its base URL
        # to https://openrouter.ai/api/v1, so only the API key is needed.
        self._client = OpenRouter(api_key=api_key)
        self._model = model

    def _generate(self, prompt: str) -> str | None:
        from openrouter.components.chatusermessage import (  # noqa: PLC0415
            ChatUserMessage,
        )
        from openrouter.components.providerpreferences import (  # noqa: PLC0415
            ProviderPreferences,
        )

        response = self._client.chat.send(
            model=self._model,
            messages=[ChatUserMessage(role="user", content=prompt)],
            stream=False,
            # Incident Slack content goes to a third party, so require
            # zero-data-retention routing.
            provider=ProviderPreferences(zdr=True),
        )
        content = (
            response.choices[0].message.content
            if response and response.choices
            else None
        )
        # OpenRouter allows structured content parts, but a text completion
        # returns a plain string; ignore anything non-str defensively.
        return content if isinstance(content, str) and content else None

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

                for reply in msg.get("replies", []):
                    rts = reply["date_time"].strftime("%Y-%m-%d %H:%M:%S UTC")
                    rauthor = reply.get("author") or "Unknown"
                    rtext = reply.get("text", "")
                    formatted.append(f"  -> [{rts}] {rauthor}: {rtext}")

            context = (
                f"Incident Summary: {incident_summary}\n\n" if incident_summary else ""
            )
            prompt = (
                _TIMELINE_PROMPT_PREFIX
                + context
                + "Slack Channel Messages:\n"
                + "\n".join(formatted)
                + _TIMELINE_PROMPT_SUFFIX
            )

            content = self._generate(prompt)
            if content:
                logger.info("Successfully generated timeline using OpenRouter")
                return content

            logger.warning("OpenRouter returned empty response for timeline generation")
            return None

        except Exception:
            logger.exception("Failed to generate timeline with OpenRouter")
            return None
