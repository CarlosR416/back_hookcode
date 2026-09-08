"""
Serializers for the routers application.
"""

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import Router, UserRouter

User = get_user_model()


class RouterSerializer(serializers.ModelSerializer):
    """Read serializer — never exposes the api_password."""

    api_port = serializers.IntegerField(
        read_only=True,
        help_text=_("Port used for MikroTik REST API connections (base port + 5000)."),
    )
    winbox_port = serializers.IntegerField(
        read_only=True,
        help_text=_("Port used for MikroTik Winbox management (identical to base port)."),
    )

    class Meta:
        model = Router
        fields = [
            "id",
            "name",
            "host",
            "port",
            "api_port",
            "winbox_port",
            "api_username",
            "ssl_verify",
            "routeros_version",
            "is_active",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "api_port", "winbox_port", "created_at", "updated_at"]


class RouterWriteSerializer(serializers.ModelSerializer):
    """Write serializer — accepts api_password on create/update."""

    class Meta:
        model = Router
        fields = [
            "id",
            "name",
            "host",
            "port",
            "api_username",
            "api_password",
            "ssl_verify",
            "routeros_version",
            "is_active",
            "description",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "api_password": {"write_only": True},
        }


class RouterCreateSerializer(serializers.ModelSerializer):
    """
    Client registration serializer.

    Only accepts name and description from the client.
    Host, port, credentials, and RouterOS version are provisioned
    automatically by backend services.
    """

    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text=_("Optional router description."),
    )

    class Meta:
        model = Router
        fields = ["id", "name", "description"]
        read_only_fields = ["id"]


# ---------------------------------------------------------------------------
# UserRouter serializers
# ---------------------------------------------------------------------------


class UserRouterSerializer(serializers.ModelSerializer):
    """
    Read serializer for user-router associations.

    Exposes nested router info and the user's email for clarity.
    Never exposes API credentials (RouterSerializer is used, not RouterWriteSerializer).
    """

    router = RouterSerializer(read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = UserRouter
        fields = ["id", "user_email", "router", "role", "created_at"]
        read_only_fields = ["id", "created_at"]


class UserRouterWriteSerializer(serializers.ModelSerializer):
    """
    Write serializer for creating / updating user-router associations.

    The `user` field defaults to the requesting user when not explicitly provided.
    """

    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        default=serializers.CurrentUserDefault(),
    )

    class Meta:
        model = UserRouter
        fields = ["user", "router", "role"]
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=UserRouter.objects.all(),
                fields=["user", "router"],
                message=_("This user already has a role assigned for the selected router."),
            )
        ]

