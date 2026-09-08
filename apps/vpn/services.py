"""
Service layer for the VPN application.

Provides high-level APIs for interacting with VPN server nodes and serving public certificates.
"""

from typing import Any
from django.core.exceptions import ObjectDoesNotExist

from .models import VpnNode


class VpnNodeService:
    """
    Service for VPN node management and public certificate retrieval.
    """

    @classmethod
    def resolve_node(cls, node_or_identifier: VpnNode | int | str) -> VpnNode:
        """
        Resolve a VpnNode from an instance, integer ID, or unique name.
        Only resolves active nodes unless an existing instance is passed.
        """
        if isinstance(node_or_identifier, VpnNode):
            if not node_or_identifier.is_active:
                raise ValueError(f"VPN node '{node_or_identifier.name}' is inactive.")
            return node_or_identifier

        if isinstance(node_or_identifier, int):
            try:
                return VpnNode.objects.get(pk=node_or_identifier, is_active=True)
            except VpnNode.DoesNotExist:
                raise ObjectDoesNotExist(
                    f"Active VPN node with ID {node_or_identifier} does not exist."
                )

        if isinstance(node_or_identifier, str):
            try:
                return VpnNode.objects.get(name=node_or_identifier, is_active=True)
            except VpnNode.DoesNotExist:
                raise ObjectDoesNotExist(
                    f"Active VPN node with name '{node_or_identifier}' does not exist."
                )

        raise TypeError(
            f"Expected VpnNode, int, or str, got {type(node_or_identifier).__name__}."
        )

    @classmethod
    def get_public_certificate(cls, node_or_identifier: VpnNode | int | str) -> str:
        """
        Serve the public certificate or public key for the specified active VPN node.

        :param node_or_identifier: VpnNode instance, integer ID, or node name.
        :return: Public certificate or key string.
        """
        node = cls.resolve_node(node_or_identifier)
        if not node.public_certificate:
            raise ValueError(f"VPN node '{node.name}' has no public certificate configured.")
        return node.public_certificate.strip()

    @classmethod
    def get_node_details(cls, node_or_identifier: VpnNode | int | str) -> dict[str, Any]:
        """
        Retrieve structured connection and certificate details for a VPN node.
        """
        node = cls.resolve_node(node_or_identifier)
        return {
            "id": node.pk,
            "name": node.name,
            "host": node.host,
            "port": node.port,
            "vpn_type": node.vpn_type,
            "public_certificate": node.public_certificate.strip(),
            "is_active": node.is_active,
        }
