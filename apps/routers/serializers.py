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

    class Meta:
        model = Router
        fields = [
            "id",
            "name",
            "host",
            "port",
            "api_username",
            "ssl_verify",
            "routeros_version",
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
            "routeros_version",
            "is_active",
            "description",
        ]
        extra_kwargs = {
            "api_password": {"write_only": True},
        }


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

