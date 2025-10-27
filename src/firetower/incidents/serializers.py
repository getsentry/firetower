from rest_framework import serializers

from firetower.auth.serializers import UserSerializer

from .models import Incident


class IncidentListSerializer(serializers.ModelSerializer):
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

    def get_name(self, obj):
        """Get user's full name or username"""
        return obj.get_full_name() or obj.username

    def get_role(self, obj):
        """Determine role based on incident context"""
        incident = self.context.get("incident")
        if not incident:
            return "Participant"

        if incident.captain == obj:
            return "Captain"
        elif incident.reporter == obj:
            return "Reporter"
        return "Participant"


class IncidentDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for incident detail view.

    Matches frontend expectations from transformers.py
    """

    # Use incident_number as "id" field for frontend compatibility
    id = serializers.CharField(source="incident_number", read_only=True)

    # Full nested user data for captain/reporter
    captain = UserSerializer(read_only=True)
    reporter = UserSerializer(read_only=True)

    # Participants with role information
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
            "captain",
            "reporter",
            "participants",
            "affected_areas",
            "root_causes",
            "external_links",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_participants(self, obj):
        """
        Get all participants with their roles.

        Combines captain, reporter, and participants into one list
        matching frontend expectation.
        """
        participants_list = []
        seen_users = set()

        # Add captain
        if obj.captain and obj.captain.id not in seen_users:
            serializer = ParticipantSerializer(obj.captain, context={"incident": obj})
            participants_list.append(serializer.data)
            seen_users.add(obj.captain.id)

        # Add reporter
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
