"""
Serializers for the hotspot application.
"""

from rest_framework import serializers

from .models import HotspotProfile, HotspotTemplate, HotspotTemplateFile, HotspotUser


class HotspotProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotspotProfile
        fields = [
            "id",
            "router",
            "mk_id",
            "name",
            "rate_limit",
            "session_timeout",
            "shared_users",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "mk_id", "created_at", "updated_at"]


class HotspotUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotspotUser
        fields = [
            "id",
            "router",
            "profile",
            "mk_id",
            "username",
            "comment",
            "is_disabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "mk_id", "created_at", "updated_at"]


class HotspotUserWriteSerializer(serializers.ModelSerializer):
    """Write serializer — includes password for router creation."""

    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = HotspotUser
        fields = [
            "router",
            "profile",
            "username",
            "password",
            "comment",
        ]


# ---------------------------------------------------------------------------
# HotspotTemplate serializers
# ---------------------------------------------------------------------------


class HotspotTemplateFileSerializer(serializers.ModelSerializer):
    """Read serializer for a single template file (no content by default)."""

    class Meta:
        model = HotspotTemplateFile
        fields = [
            "id",
            "filename",
            "role",
            "mime_type",
            "order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class HotspotTemplateFileDetailSerializer(serializers.ModelSerializer):
    """Read serializer that includes the full Jinja2 content — used on retrieve."""

    class Meta:
        model = HotspotTemplateFile
        fields = [
            "id",
            "template",
            "filename",
            "role",
            "content",
            "mime_type",
            "order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class HotspotTemplateFileWriteSerializer(serializers.ModelSerializer):
    """Write serializer for creating / updating a template file."""

    class Meta:
        model = HotspotTemplateFile
        fields = ["template", "filename", "role", "content", "mime_type", "order"]

    def validate_filename(self, value: str) -> str:
        """Reject filenames with path separators to prevent directory traversal."""
        if "/" in value or "\\" in value:
            raise serializers.ValidationError(
                "Filename must not contain path separators ('/' or '\\')."
            )
        return value


class HotspotTemplateSerializer(serializers.ModelSerializer):
    """
    Read serializer for HotspotTemplate.
    Includes a lightweight summary of each file (no content bulk).
    """

    files = HotspotTemplateFileSerializer(many=True, read_only=True)
    created_by_email = serializers.EmailField(
        source="created_by.email", read_only=True, default=None
    )

    class Meta:
        model = HotspotTemplate
        fields = [
            "id",
            "name",
            "description",
            "vendor",
            "variables",
            "is_active",
            "created_by_email",
            "files",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by_email", "created_at", "updated_at"]


class HotspotTemplateWriteSerializer(serializers.ModelSerializer):
    """Write serializer — used for create / update of the template header."""

    class Meta:
        model = HotspotTemplate
        fields = ["name", "description", "vendor", "variables", "is_active"]
