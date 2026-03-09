"""
Serializers for the hotspot application.
"""

from rest_framework import serializers

from .models import HotspotProfile, HotspotUser


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
