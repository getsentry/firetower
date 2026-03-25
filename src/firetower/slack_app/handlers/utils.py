from firetower.incidents.models import ExternalLink, ExternalLinkType, Incident


def get_incident_from_channel(channel_id: str) -> Incident | None:
    link = ExternalLink.objects.filter(
        type=ExternalLinkType.SLACK,
        url__contains=channel_id,
    ).first()
    if link:
        return link.incident
    return None
