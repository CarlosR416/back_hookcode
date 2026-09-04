"""
Serializers for the tickets application.
"""

from rest_framework import serializers

from .models import Ticket


class TicketSerializer(serializers.ModelSerializer):
    """Read serializer — returns the full ticket representation."""

    class Meta:
        model = Ticket
        fields = [
            "id",
            "router",
            "code",
            "profile_name",
            "duration_minutes",
            "status",
            "mk_user_id",
            "activated_at",
            "comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "status", "mk_user_id", "activated_at", "created_at", "updated_at"]


class TicketBulkGenerateSerializer(serializers.Serializer):
    """Input serializer for bulk ticket generation."""

    router = serializers.PrimaryKeyRelatedField(queryset=__import__("apps.routers.models", fromlist=["Router"]).Router.objects.filter(is_active=True))
    profile_name = serializers.CharField(max_length=100)
    duration_minutes = serializers.IntegerField(min_value=1, default=60)
    quantity = serializers.IntegerField(min_value=1, max_value=500, default=10)
    comment = serializers.CharField(max_length=500, required=False, default="")


class TicketActivateSerializer(serializers.Serializer):
    """Input serializer for ticket activation (optionally override username)."""

    username = serializers.CharField(max_length=100, required=False, allow_blank=True)
