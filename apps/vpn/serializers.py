"""
Serializers for the VPN application.
"""

from rest_framework import serializers

from .models import VpnNode


class VpnNodeSerializer(serializers.ModelSerializer):
    """
    Representation of a VPN Node.
    """

    vpn_type_display = serializers.CharField(
        source="get_vpn_type_display", read_only=True
    )

    class Meta:
        model = VpnNode
        fields = [
            "id",
            "name",
            "host",
            "port",
            "internal_ip",
            "vpn_type",
            "vpn_type_display",
            "public_certificate",
            "is_active",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class VpnNodeWriteSerializer(serializers.ModelSerializer):
    """
    Write serializer for creating or updating a VPN Node.
    """

    class Meta:
        model = VpnNode
        fields = [
            "name",
            "host",
            "port",
            "internal_ip",
            "vpn_type",
            "public_certificate",
            "is_active",
            "description",
        ]


class VpnNodeCertificateSerializer(serializers.Serializer):
    """
    Response envelope for serving a VPN node's public certificate.
    """

    node_id = serializers.IntegerField(help_text="ID of the VPN node.")
    name = serializers.CharField(help_text="Name of the VPN node.")
    vpn_type = serializers.CharField(help_text="Protocol/type of VPN.")
    public_certificate = serializers.CharField(
        help_text="Public certificate (PEM format) or public key."
    )
