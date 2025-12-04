from dataclasses import dataclass
from typing import Any

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import ExternalLink, ExternalLinkType, Incident, Tag, TagType


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
    captain = serializers.SerializerMethodField()
    reporter = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()
    affected_areas = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )
    root_causes = serializers.ListField(child=serializers.CharField(), read_only=True)
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
            "affected_areas",
            "root_causes",
            "external_links",
            "created_at",
            "updated_at",
        ]

    def get_captain(self, obj: Incident) -> str | None:
        """Return captain email or None if not set"""
        return obj.captain.email if obj.captain else None

    def get_reporter(self, obj: Incident) -> str | None:
        """Return reporter email or None if not set"""
        return obj.reporter.email if obj.reporter else None

    def get_participants(self, obj: Incident) -> list[str]:
        """Return list of participant emails"""
        return [user.email for user in obj.participants.all()]


class IncidentWriteSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating incidents via the service API.

    Required fields: title, severity, is_private, captain, reporter
    Optional fields: description, impact, status, external_links,
                     affected_areas, root_causes

    external_links format: {"slack": "url", "jira": "url", ...}
    - Merges with existing links (only updates provided links)
    - Use null to delete a specific link: {"slack": null}
    - Omit external_links field to leave existing links unchanged

    affected_areas/root_causes format: ["tag1", "tag2", ...]
    - Replaces all existing tags with the provided list
    - Tags must already exist (create via POST /api/tags/)
    - Omit field to leave existing tags unchanged
    """

    id = serializers.CharField(source="incident_number", read_only=True)
    external_links = serializers.DictField(
        child=serializers.CharField(allow_null=True),
        required=False,
        allow_null=False,
        write_only=True,
    )
    affected_areas = serializers.SerializerMethodField()
    root_causes = serializers.SerializerMethodField()

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
            "affected_areas",
            "root_causes",
        ]
        extra_kwargs = {
            "captain": {"required": True},
            "reporter": {"required": True},
            "is_private": {"required": True},
        }

    def get_affected_areas(self, obj: Incident) -> list[str]:
        return list(obj.affected_area_tags.values_list("name", flat=True))

    def get_root_causes(self, obj: Incident) -> list[str]:
        return list(obj.root_cause_tags.values_list("name", flat=True))

    def to_internal_value(self, data: dict) -> dict:
        # Extract tag fields before standard validation (since SerializerMethodField is read-only)
        affected_areas = data.get("affected_areas")
        root_causes = data.get("root_causes")

        result = super().to_internal_value(data)

        # Add back tag fields if provided, with validation
        if affected_areas is not None:
            if not isinstance(affected_areas, list):
                raise serializers.ValidationError(
                    {"affected_areas": ["Expected a list of strings."]}
                )
            for tag_name in affected_areas:
                if not Tag.objects.filter(
                    name__iexact=tag_name, type=TagType.AFFECTED_AREA
                ).exists():
                    raise serializers.ValidationError(
                        {
                            "affected_areas": [
                                f"Tag '{tag_name}' does not exist for type AFFECTED_AREA"
                            ]
                        }
                    )
            result["affected_areas"] = affected_areas

        if root_causes is not None:
            if not isinstance(root_causes, list):
                raise serializers.ValidationError(
                    {"root_causes": ["Expected a list of strings."]}
                )
            for tag_name in root_causes:
                if not Tag.objects.filter(
                    name__iexact=tag_name, type=TagType.ROOT_CAUSE
                ).exists():
                    raise serializers.ValidationError(
                        {
                            "root_causes": [
                                f"Tag '{tag_name}' does not exist for type ROOT_CAUSE"
                            ]
                        }
                    )
            result["root_causes"] = root_causes

        return result

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
        validated_data.pop("affected_areas", None)
        validated_data.pop("root_causes", None)

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
        Update incident with merge behavior for external links and tag replacement.

        Only updates fields provided in the request (partial update).
        External links are merged - only provided links are updated/deleted.
        Tags are replaced - the provided list replaces all existing tags.
        """
        external_links_data = validated_data.pop("external_links", None)
        affected_areas_data = validated_data.pop("affected_areas", None)
        root_causes_data = validated_data.pop("root_causes", None)

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

        # Replace affected area tags if provided
        if affected_areas_data is not None:
            tags = Tag.objects.filter(
                name__in=affected_areas_data, type=TagType.AFFECTED_AREA
            )
            instance.affected_area_tags.set(tags)

        # Replace root cause tags if provided
        if root_causes_data is not None:
            tags = Tag.objects.filter(
                name__in=root_causes_data, type=TagType.ROOT_CAUSE
            )
            instance.root_cause_tags.set(tags)

        return instance


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["name"]

    def to_representation(self, instance: Tag) -> str:
        return instance.name


class TagCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["name", "type"]

    def create(self, validated_data: dict[str, Any]) -> Tag:
        try:
            return Tag.objects.create(**validated_data)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)
