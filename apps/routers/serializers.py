"""
Serializers for the routers application.
"""

from rest_framework import serializers

from .models import Router


class RouterSerializer(serializers.ModelSerializer):
    """Read serializer — never exposes the api_password."""

    class Meta:
        model = Router
        fields = [
            "id",
            "name",
            "host",
            "port",
            "api_username",
            "ssl_verify",
            "is_active",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class RouterWriteSerializer(serializers.ModelSerializer):
    """Write serializer — accepts api_password on create/update."""

    class Meta:
        model = Router
        fields = [
            "name",
            "host",
            "port",
            "api_username",
            "api_password",
            "ssl_verify",
            "is_active",
            "description",
        ]
        extra_kwargs = {
            "api_password": {"write_only": True},
        }
