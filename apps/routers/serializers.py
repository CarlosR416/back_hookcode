"""
Serializers for the routers application.
"""

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import Router, UserRouter

User = get_user_model()


class RouterVpnConnectionSerializer(serializers.Serializer):
    """Structured representation of the router's VPN connection status."""

    status = serializers.ChoiceField(
        choices=["NEVER_CONNECTED", "CONNECTED", "DISCONNECTED"],
        help_text=_("VPN connection status deduced from FreeRADIUS accounting records."),
    )
    is_connected = serializers.BooleanField(
        help_text=_("Whether the router is currently connected to the VPN server."),
    )
    tunnel_ip = serializers.CharField(
        allow_null=True,
        help_text=_("Internal tunnel IP address assigned to the router by the VPN server."),
    )
    connected_at = serializers.DateTimeField(
        allow_null=True,
        help_text=_("Timestamp when the current or last VPN session started."),
    )
    last_seen = serializers.DateTimeField(
        allow_null=True,
        help_text=_("Timestamp when the last VPN session ended."),
    )


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
    vpn_connection = serializers.SerializerMethodField(
        help_text=_("Structured VPN connection info queried from FreeRADIUS accounting."),
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
            "vpn_connection",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "api_port",
            "winbox_port",
            "vpn_connection",
            "created_at",
            "updated_at",
        ]

    def get_vpn_connection(self, obj: Router) -> dict:
        vpn_cache = self.context.get("vpn_connections_map")
        if vpn_cache is not None and obj.id in vpn_cache:
            return vpn_cache[obj.id]
        return obj.vpn_connection_info


class RouterListSerializer(serializers.ModelSerializer):
    """
    List serializer — omits internal IP addresses (router host and vpn_connection.tunnel_ip).
    """

    api_port = serializers.IntegerField(
        read_only=True,
        help_text=_("Port used for MikroTik REST API connections (base port + 5000)."),
    )
    winbox_port = serializers.IntegerField(
        read_only=True,
        help_text=_("Port used for MikroTik Winbox management (identical to base port)."),
    )
    vpn_connection = serializers.SerializerMethodField(
        help_text=_("Structured VPN connection info without internal tunnel IP."),
    )

    class Meta:
        model = Router
        fields = [
            "id",
            "name",
            "port",
            "api_port",
            "winbox_port",
            "api_username",
            "ssl_verify",
            "routeros_version",
            "is_active",
            "description",
            "vpn_connection",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "api_port",
            "winbox_port",
            "vpn_connection",
            "created_at",
            "updated_at",
        ]

    def get_vpn_connection(self, obj: Router) -> dict:
        vpn_cache = self.context.get("vpn_connections_map")
        if vpn_cache is not None and obj.id in vpn_cache:
            info = vpn_cache[obj.id]
        else:
            info = obj.vpn_connection_info

        return {
            "status": info.get("status", "NEVER_CONNECTED"),
            "is_connected": info.get("is_connected", False),
            "connected_at": info.get("connected_at"),
            "last_seen": info.get("last_seen"),
        }


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

    def validate(self, attrs: dict) -> dict:
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            user = request.user
            if not getattr(user, "can_add_router", True):
                raise serializers.ValidationError(
                    _(
                        "You have reached the maximum limit of %(limit)d routers allowed for the free plan."
                    )
                    % {"limit": getattr(user, "max_routers", 3)}
                )
        return attrs


class GenerateVpnTokenSerializer(serializers.Serializer):
    """Input serializer for generating an automated IKEv2 VPN client provisioning token."""

    expiration_minutes = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=60,
        default=10,
        help_text=_("Token expiration in minutes (default 10)."),
    )
    filename = serializers.CharField(
        required=False,
        default="vpn_setup.rsc",
        max_length=100,
        help_text=_("Destination filename on the MikroTik router."),
    )


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

