from dataclasses import dataclass

from django.contrib.auth.models import User
from rest_framework import serializers

from .models import ExternalLink, ExternalLinkType, Incident


@dataclass
class ParticipantData:
    """Structure of serialized participant data."""

    name: str
    avatar_url: str | None
    role: str


class IncidentListUISerializer(serializers.ModelSerializer):
    """
    Serializer for listing incidents.

    Minimal fields for list views - just core incident data.
    """

    # Use incident_number as "id" field for frontend
    id = serializers.CharField(source="incident_number", read_only=True)

    class Meta:
        model = Incident
        fields = [
            "id",
            "title",
            "description",
            "impact",
            "status",
            "severity",
            "is_private",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ParticipantSerializer(serializers.Serializer):
    """
    Serializer for participants in incident detail view.

    Matches frontend expectation: {name, avatar_url, role}
    """

    name = serializers.SerializerMethodField()
    avatar_url = serializers.CharField(source="userprofile.avatar_url", read_only=True)
    role = serializers.SerializerMethodField()

    def get_name(self, obj: User) -> str:
        """Get user's full name or username"""
        return obj.get_full_name() or obj.username

    def get_role(self, obj: User) -> str:
        """Determine role based on incident context"""
        incident = self.context.get("incident")
        if not incident:
            return "Participant"

        if incident.captain == obj:
            return "Captain"
        elif incident.reporter == obj:
            return "Reporter"
        return "Participant"


class IncidentDetailUISerializer(serializers.ModelSerializer):
    """
    Serializer for incident detail view.

    Matches frontend expectations from transformers.py
    """

    # Use incident_number as "id" field for frontend compatibility
    id = serializers.CharField(source="incident_number", read_only=True)

    # Full nested user data for captain/reporter
    # Participants with role information (includes captain and reporter)
    participants = serializers.SerializerMethodField()

    # Tags as arrays of strings (not full objects)
    affected_areas = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )
    root_causes = serializers.ListField(child=serializers.CharField(), read_only=True)

    # External links as dict for easy frontend access
    external_links = serializers.DictField(source="external_links_dict", read_only=True)

    class Meta:
        model = Incident
        fields = [
            "id",
            "title",
            "description",
            "impact",
            "status",
            "severity",
            "is_private",
            "participants",
            "affected_areas",
            "root_causes",
            "external_links",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_participants(self, obj: Incident) -> list[ParticipantData]:
        """
        Get all participants with their roles, with captain and reporter at the top.

        Order:
        1. Captain (if exists)
        2. Reporter (if exists)
        3. Other participants
        """
        participants_list = []
        seen_users = set()

        # Add captain first
        if obj.captain and obj.captain.id not in seen_users:
            serializer = ParticipantSerializer(obj.captain, context={"incident": obj})
            participants_list.append(serializer.data)
            seen_users.add(obj.captain.id)

        # Add reporter second
        if obj.reporter and obj.reporter.id not in seen_users:
            serializer = ParticipantSerializer(obj.reporter, context={"incident": obj})
            participants_list.append(serializer.data)
            seen_users.add(obj.reporter.id)

        # Add other participants
        for participant in obj.participants.all():
            if participant.id not in seen_users:
                serializer = ParticipantSerializer(
                    participant, context={"incident": obj}
                )
                participants_list.append(serializer.data)
                seen_users.add(participant.id)

        return participants_list


class IncidentReadSerializer(serializers.ModelSerializer):
    """
    Serializer for reading incidents via the service API.

    Returns all incident data with simplified formats:
    - captain/reporter/participants as emails
    - tags as lists of strings
    - external_links as dict
    """

    id = serializers.CharField(source="incident_number", read_only=True)
    captain = serializers.EmailField(source="captain.email", read_only=True)
    reporter = serializers.EmailField(source="reporter.email", read_only=True)
    participants = serializers.SerializerMethodField()
    affected_area_tags = serializers.ListField(
        child=serializers.CharField(), source="affected_areas", read_only=True
    )
    root_cause_tags = serializers.ListField(
        child=serializers.CharField(), source="root_causes", read_only=True
    )
    external_links = serializers.DictField(source="external_links_dict", read_only=True)

    class Meta:
        model = Incident
        fields = [
            "id",
            "title",
            "description",
            "impact",
            "status",
            "severity",
            "is_private",
            "captain",
            "reporter",
            "participants",
            "affected_area_tags",
            "root_cause_tags",
            "external_links",
            "created_at",
            "updated_at",
        ]

    def get_participants(self, obj: Incident) -> list[str]:
        """Return list of participant emails"""
        return [user.email for user in obj.participants.all()]


class IncidentWriteSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating incidents via the service API.

    Required fields: title, severity, is_private, captain, reporter
    Optional fields: description, impact, status, external_links

    external_links format: {"slack": "url", "jira": "url", ...}
    - Merges with existing links (only updates provided links)
    - Use null to delete a specific link: {"slack": null}
    - Omit external_links field to leave existing links unchanged
    """

    id = serializers.CharField(source="incident_number", read_only=True)
    external_links = serializers.DictField(
        child=serializers.CharField(allow_null=True),
        required=False,
        allow_null=False,
        write_only=True,
    )

    class Meta:
        model = Incident
        fields = [
            "id",
            "title",
            "description",
            "impact",
            "status",
            "severity",
            "is_private",
            "captain",
            "reporter",
            "external_links",
        ]
        extra_kwargs = {
            "captain": {"required": True},
            "reporter": {"required": True},
            "is_private": {"required": True},
        }

    def validate_external_links(
        self, value: dict[str, str | None]
    ) -> dict[str, str | None]:
        """Validate external link types and URLs"""
        valid_types = [link_type.lower() for link_type in ExternalLinkType.values]

        for link_type, url in value.items():
            if link_type.lower() not in valid_types:
                raise serializers.ValidationError(
                    f"Invalid link type '{link_type}'. Must be one of: {', '.join(valid_types)}"
                )

            # Validate URL format if not null
            if url is not None:
                url_validator = serializers.URLField()
                try:
                    url_validator.run_validation(url)
                except serializers.ValidationError as e:
                    raise serializers.ValidationError(
                        f"Invalid URL for {link_type}: {e.detail[0]}"
                    )

        return value

    def create(self, validated_data: dict) -> Incident:
        """Create incident with external links"""
        external_links_data = validated_data.pop("external_links", None)

        # Create the incident
        incident = super().create(validated_data)

        # Create external links if provided
        if external_links_data:
            for link_type, url in external_links_data.items():
                if url is not None:  # Skip null values on create
                    ExternalLink.objects.create(
                        incident=incident,
                        type=link_type.upper(),
                        url=url,
                    )

        return incident

    def update(self, instance: Incident, validated_data: dict) -> Incident:
        """
        Update incident with merge behavior for external links.

        Only updates fields provided in the request (partial update).
        External links are merged - only provided links are updated/deleted.
        """
        external_links_data = validated_data.pop("external_links", None)

        # Update basic fields
        instance = super().update(instance, validated_data)

        # Merge external links if provided
        if external_links_data is not None:
            for link_type, url in external_links_data.items():
                link_type_upper = link_type.upper()

                if url is None:
                    # Delete the link
                    ExternalLink.objects.filter(
                        incident=instance, type=link_type_upper
                    ).delete()
                else:
                    # Create or update the link
                    ExternalLink.objects.update_or_create(
                        incident=instance,
                        type=link_type_upper,
                        defaults={"url": url},
                    )

        return instance
