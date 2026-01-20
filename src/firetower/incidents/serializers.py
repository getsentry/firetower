from dataclasses import dataclass
from typing import Any

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models.functions import Lower
from rest_framework import serializers

from firetower.auth.services import get_or_create_user_from_email

from .models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentOrRedirect,
    Tag,
    TagType,
)


@dataclass
class ParticipantData:
    """Structure of serialized participant data."""

    name: str
    avatar_url: str | None
    role: str
    email: str


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
            "impact_summary",
            "status",
            "severity",
            "service_tier",
            "is_private",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ParticipantSerializer(serializers.Serializer):
    """
    Serializer for participants in incident detail view.

    Matches frontend expectation: {name, avatar_url, role, email}
    """

    name = serializers.SerializerMethodField()
    avatar_url = serializers.CharField(source="userprofile.avatar_url", read_only=True)
    role = serializers.SerializerMethodField()
    email = serializers.EmailField(read_only=True)

    def get_name(self, obj: User) -> str:
        """Get user's full name or username"""
        return obj.get_full_name() or obj.username

    def get_role(self, obj: User) -> str:
        """Get role from context, or determine based on incident"""
        # If role is explicitly provided in context, use it
        explicit_role = self.context.get("role")
        if explicit_role:
            return explicit_role

        # Otherwise determine from incident
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
    affected_service_tags = serializers.ListField(
        child=serializers.CharField(),
        source="affected_service_tag_names",
        read_only=True,
    )
    root_cause_tags = serializers.ListField(
        child=serializers.CharField(), source="root_cause_tag_names", read_only=True
    )
    impact_type_tags = serializers.ListField(
        child=serializers.CharField(), source="impact_type_tag_names", read_only=True
    )
    affected_region_tags = serializers.ListField(
        child=serializers.CharField(),
        source="affected_region_tag_names",
        read_only=True,
    )

    # External links as dict for easy frontend access
    external_links = serializers.DictField(source="external_links_dict", read_only=True)

    class Meta:
        model = Incident
        fields = [
            "id",
            "title",
            "description",
            "impact_summary",
            "status",
            "severity",
            "service_tier",
            "is_private",
            "participants",
            "affected_service_tags",
            "affected_region_tags",
            "root_cause_tags",
            "impact_type_tags",
            "external_links",
            "created_at",
            "updated_at",
            "time_started",
            "time_detected",
            "time_analyzed",
            "time_mitigated",
            "time_recovered",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "time_started",
            "time_detected",
            "time_analyzed",
            "time_mitigated",
            "time_recovered",
        ]

    def get_participants(self, obj: Incident) -> list[ParticipantData]:
        """
        Get all participants with their roles, with captain and reporter at the top.

        Order:
        1. Captain (if exists)
        2. Reporter (if exists) - same user can appear twice if also captain
        3. Other participants (excluding captain/reporter)
        """
        participants_list = []
        seen_users = set()

        # Add captain first with explicit role
        if obj.captain:
            serializer = ParticipantSerializer(
                obj.captain, context={"incident": obj, "role": "Captain"}
            )
            participants_list.append(serializer.data)
            seen_users.add(obj.captain.id)

        # Add reporter second with explicit role (even if same as captain)
        if obj.reporter:
            serializer = ParticipantSerializer(
                obj.reporter, context={"incident": obj, "role": "Reporter"}
            )
            participants_list.append(serializer.data)
            seen_users.add(obj.reporter.id)

        # Add other participants (excluding those who are captain or reporter)
        for participant in obj.participants.all():
            if participant.id not in seen_users:
                serializer = ParticipantSerializer(
                    participant, context={"incident": obj, "role": "Participant"}
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
    affected_service_tags = serializers.ListField(
        child=serializers.CharField(),
        source="affected_service_tag_names",
        read_only=True,
    )
    root_cause_tags = serializers.ListField(
        child=serializers.CharField(), source="root_cause_tag_names", read_only=True
    )
    impact_type_tags = serializers.ListField(
        child=serializers.CharField(), source="impact_type_tag_names", read_only=True
    )
    affected_region_tags = serializers.ListField(
        child=serializers.CharField(),
        source="affected_region_tag_names",
        read_only=True,
    )
    external_links = serializers.DictField(source="external_links_dict", read_only=True)

    class Meta:
        model = Incident
        fields = [
            "id",
            "title",
            "description",
            "impact_summary",
            "status",
            "severity",
            "service_tier",
            "is_private",
            "captain",
            "reporter",
            "participants",
            "affected_service_tags",
            "affected_region_tags",
            "root_cause_tags",
            "impact_type_tags",
            "external_links",
            "created_at",
            "updated_at",
            "time_started",
            "time_detected",
            "time_analyzed",
            "time_mitigated",
            "time_recovered",
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


class UserEmailField(serializers.EmailField):
    """Field that accepts email and converts to User instance."""

    def run_validation(self, data: str) -> User:
        # Validate as email first (runs email format validators)
        email = super().run_validation(data)
        # Get or create user from email (provisions from Slack if needed)
        user = get_or_create_user_from_email(email)
        if user is None:
            raise serializers.ValidationError(
                f"Could not create user with email '{email}'"
            )
        return user

    def to_representation(self, value: User | None) -> str | None:
        return value.email if value else None


class IncidentWriteSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating incidents via the service API.

    Required fields: title, severity, captain, reporter
    Optional fields: description, impact_summary, status, is_private (default: False),
                     external_links, affected_service_tags, affected_region_tags,
                     root_cause_tags, impact_type_tags

    captain/reporter: Email address of the user
    external_links format: {"slack": "url", "jira": "url", ...}
    - Merges with existing links (only updates provided links)
    - Use null to delete a specific link: {"slack": null}
    - Omit external_links field to leave existing links unchanged

    affected_service_tags/affected_region_tags/root_cause_tags/impact_type_tags format: ["tag1", "tag2", ...]
    - Replaces all existing tags with the provided list
    - Tags must already exist (create via POST /api/tags/)
    - Omit field to leave existing tags unchanged
    """

    id = serializers.CharField(source="incident_number", read_only=True)
    captain = UserEmailField(required=True)
    reporter = UserEmailField(required=True)
    external_links = serializers.DictField(
        child=serializers.CharField(allow_null=True),
        required=False,
        allow_null=False,
        write_only=True,
    )
    affected_service_tags = serializers.ListField(
        child=serializers.CharField(),
        source="affected_service_tag_names",
        required=False,
    )
    root_cause_tags = serializers.ListField(
        child=serializers.CharField(), source="root_cause_tag_names", required=False
    )
    impact_type_tags = serializers.ListField(
        child=serializers.CharField(), source="impact_type_tag_names", required=False
    )
    affected_region_tags = serializers.ListField(
        child=serializers.CharField(),
        source="affected_region_tag_names",
        required=False,
    )

    class Meta:
        model = Incident
        fields = [
            "id",
            "title",
            "description",
            "impact_summary",
            "status",
            "severity",
            "service_tier",
            "is_private",
            "captain",
            "reporter",
            "external_links",
            "affected_service_tags",
            "affected_region_tags",
            "root_cause_tags",
            "impact_type_tags",
            "time_started",
            "time_detected",
            "time_analyzed",
            "time_mitigated",
            "time_recovered",
        ]
        extra_kwargs = {
            "is_private": {"required": False},
            "service_tier": {"required": False},
        }

    def _validate_tags_exist(self, value: list[str], tag_type: str) -> list[str]:
        value_lower = {v.lower() for v in value}
        existing = set(
            Tag.objects.filter(type=tag_type)
            .annotate(name_lower=Lower("name"))
            .filter(name_lower__in=value_lower)
            .values_list("name_lower", flat=True)
        )
        missing = [v for v in value if v.lower() not in existing]
        if missing:
            raise serializers.ValidationError(
                f"Tag '{missing[0]}' does not exist for type {tag_type}"
            )
        return value

    def validate_affected_service_tags(self, value: list[str]) -> list[str]:
        return self._validate_tags_exist(value, TagType.AFFECTED_SERVICE)

    def validate_root_cause_tags(self, value: list[str]) -> list[str]:
        return self._validate_tags_exist(value, TagType.ROOT_CAUSE)

    def validate_impact_type_tags(self, value: list[str]) -> list[str]:
        return self._validate_tags_exist(value, TagType.IMPACT_TYPE)

    def validate_affected_region_tags(self, value: list[str]) -> list[str]:
        return self._validate_tags_exist(value, TagType.AFFECTED_REGION)

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
        """Create incident with external links and tags"""
        external_links_data = validated_data.pop("external_links", None)
        affected_service_tag_names = validated_data.pop(
            "affected_service_tag_names", None
        )
        affected_region_tag_names = validated_data.pop(
            "affected_region_tag_names", None
        )
        root_cause_tag_names = validated_data.pop("root_cause_tag_names", None)
        impact_type_tag_names = validated_data.pop("impact_type_tag_names", None)

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

        # Set tags if provided
        if affected_service_tag_names:
            tags = Tag.objects.annotate(name_lower=Lower("name")).filter(
                name_lower__in=[n.lower() for n in affected_service_tag_names],
                type=TagType.AFFECTED_SERVICE,
            )
            incident.affected_service_tags.set(tags)

        if affected_region_tag_names:
            tags = Tag.objects.annotate(name_lower=Lower("name")).filter(
                name_lower__in=[n.lower() for n in affected_region_tag_names],
                type=TagType.AFFECTED_REGION,
            )
            incident.affected_region_tags.set(tags)

        if root_cause_tag_names:
            tags = Tag.objects.annotate(name_lower=Lower("name")).filter(
                name_lower__in=[n.lower() for n in root_cause_tag_names],
                type=TagType.ROOT_CAUSE,
            )
            incident.root_cause_tags.set(tags)

        if impact_type_tag_names:
            tags = Tag.objects.annotate(name_lower=Lower("name")).filter(
                name_lower__in=[n.lower() for n in impact_type_tag_names],
                type=TagType.IMPACT_TYPE,
            )
            incident.impact_type_tags.set(tags)

        return incident

    def update(self, instance: Incident, validated_data: dict) -> Incident:
        """
        Update incident with merge behavior for external links and tag replacement.

        Only updates fields provided in the request (partial update).
        External links are merged - only provided links are updated/deleted.
        Tags are replaced - the provided list replaces all existing tags.
        """
        external_links_data = validated_data.pop("external_links", None)
        affected_service_tag_names = validated_data.pop(
            "affected_service_tag_names", None
        )
        affected_region_tag_names = validated_data.pop(
            "affected_region_tag_names", None
        )
        root_cause_tag_names = validated_data.pop("root_cause_tag_names", None)
        impact_type_tag_names = validated_data.pop("impact_type_tag_names", None)

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

        # Replace affected service tags if provided
        if affected_service_tag_names is not None:
            tags = Tag.objects.annotate(name_lower=Lower("name")).filter(
                name_lower__in=[n.lower() for n in affected_service_tag_names],
                type=TagType.AFFECTED_SERVICE,
            )
            instance.affected_service_tags.set(tags)

        # Replace affected region tags if provided
        if affected_region_tag_names is not None:
            tags = Tag.objects.annotate(name_lower=Lower("name")).filter(
                name_lower__in=[n.lower() for n in affected_region_tag_names],
                type=TagType.AFFECTED_REGION,
            )
            instance.affected_region_tags.set(tags)

        # Replace root cause tags if provided
        if root_cause_tag_names is not None:
            tags = Tag.objects.annotate(name_lower=Lower("name")).filter(
                name_lower__in=[n.lower() for n in root_cause_tag_names],
                type=TagType.ROOT_CAUSE,
            )
            instance.root_cause_tags.set(tags)

        # Replace impact type tags if provided
        if impact_type_tag_names is not None:
            tags = Tag.objects.annotate(name_lower=Lower("name")).filter(
                name_lower__in=[n.lower() for n in impact_type_tag_names],
                type=TagType.IMPACT_TYPE,
            )
            instance.impact_type_tags.set(tags)

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


class IncidentOrRedirectReadSerializer(serializers.Serializer):
    def to_representation(self, instance: IncidentOrRedirect) -> dict[str, Any]:
        serializer = IncidentReadSerializer()
        if instance.incident:
            return {
                "incident": serializer.to_representation(instance.incident),
            }
        return {
            "redirect": instance.redirect,
        }
