"""
Serializers for the routers application.
"""

from rest_framework import serializers

from .models import Router, UserRouter


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

    The `user` field defaults to the requesting user when not provided
    (set in the view via `perform_create`).
    """

    class Meta:
        model = UserRouter
        fields = ["router", "role"]

    def validate(self, attrs):
        """Prevent duplicate user-router entries at the serializer level."""
        user = self.context["request"].user
        router = attrs["router"]
        qs = UserRouter.objects.filter(user=user, router=router)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "This user already has a role assigned for the selected router."
            )
        return attrs

