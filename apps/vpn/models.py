"""
Models for the VPN application.

Represents VPN server nodes and their connection/certificate credentials.
"""

from django.db import models


class VpnNode(models.Model):
    """
    A VPN server node hosting gateway or tunnel endpoints.
    """

    class VpnType(models.TextChoices):
        WIREGUARD = "wireguard", "WireGuard"
        OPENVPN = "openvpn", "OpenVPN"
        IPSEC = "ipsec", "IPsec"

    name = models.CharField(max_length=100, unique=True, verbose_name="Node name")
    host = models.CharField(
        max_length=255,
        verbose_name="Host or IP address",
        help_text="Public domain name or IP address reachable by VPN clients.",
    )
    port = models.PositiveIntegerField(
        default=51820,
        verbose_name="VPN port",
        help_text="Base port used by the VPN service on this node.",
    )
    vpn_type = models.CharField(
        max_length=20,
        choices=VpnType.choices,
        default=VpnType.WIREGUARD,
        verbose_name="VPN protocol/type",
    )
    public_certificate = models.TextField(
        verbose_name="Public certificate or key",
        help_text="Public certificate in PEM format or public key (e.g. WireGuard public key).",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active",
        help_text="Designates whether this VPN node is currently operational.",
    )
    description = models.TextField(blank=True, default="", verbose_name="Description")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "VPN Node"
        verbose_name_plural = "VPN Nodes"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_vpn_type_display()} - {self.host}:{self.port})"
