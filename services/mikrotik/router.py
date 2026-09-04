"""
MikroTik Router service — system-level router information operations.
"""

from .client import MikroTikClient


class RouterService:
    """
    High-level interface for MikroTik system/router information.

    Usage:
        client = MikroTikClient(host=..., username=..., password=...)
        svc = RouterService(client)
        identity = svc.get_identity()
    """

    def __init__(self, client: MikroTikClient) -> None:
        self.client = client

    def get_identity(self) -> dict:
        """Return the router's configured identity (name)."""
        return self.client.get("system/identity")

    def get_resource(self) -> dict:
        """
        Return system resource information:
        uptime, CPU load, free memory, RouterOS version, etc.
        """
        return self.client.get("system/resource")

    def list_interfaces(self) -> list[dict]:
        """Return all network interfaces configured on the router."""
        return self.client.get("interface")

    def get_interface(self, interface_id: str) -> dict:
        """Fetch details for a single interface by RouterOS ID."""
        return self.client.get(f"interface/{interface_id}")

    def list_ip_addresses(self) -> list[dict]:
        """Return all IP addresses assigned to interfaces."""
        return self.client.get("ip/address")

    def reboot(self) -> None:
        """
        Trigger a router reboot.
        WARNING: This will disconnect all active connections.
        """
        self.client.post("system/reboot")
