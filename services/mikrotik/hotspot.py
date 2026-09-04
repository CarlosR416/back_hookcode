"""
MikroTik Hotspot service — operations on ip/hotspot resources.

All methods accept a MikroTikClient instance so the caller controls
which router is targeted. This keeps the service stateless.
"""

from typing import Any

from .client import MikroTikClient


class HotspotService:
    """
    High-level interface for MikroTik Hotspot operations.

    Usage:
        client = MikroTikClient(host=..., username=..., password=...)
        svc = HotspotService(client)
        users = svc.list_users()
    """

    USERS_PATH = "ip/hotspot/user"
    ACTIVE_PATH = "ip/hotspot/active"
    PROFILES_PATH = "ip/hotspot/user/profile"

    def __init__(self, client: MikroTikClient) -> None:
        self.client = client

    # ── Hotspot Users ──────────────────────────────────────────────────────────

    def list_users(self) -> list[dict]:
        """Return all hotspot users configured on the router."""
        return self.client.get(self.USERS_PATH)

    def get_user(self, user_id: str) -> dict:
        """Fetch a single hotspot user by its RouterOS ID."""
        return self.client.get(f"{self.USERS_PATH}/{user_id}")

    def create_user(
        self,
        name: str,
        password: str,
        profile: str = "default",
        comment: str = "",
        limit_uptime: str = "",
        limit_bytes_total: int = 0,
    ) -> dict:
        """Create a new hotspot user and return the created resource."""
        payload: dict[str, Any] = {
            "name": name,
            "password": password,
            "profile": profile,
        }
        if comment:
            payload["comment"] = comment
        if limit_uptime:
            payload["limit-uptime"] = limit_uptime
        if limit_bytes_total:
            payload["limit-bytes-total"] = limit_bytes_total

        return self.client.post(self.USERS_PATH, json=payload)

    def update_user(self, user_id: str, data: dict) -> dict:
        """Partially update a hotspot user (PATCH semantics)."""
        return self.client.patch(f"{self.USERS_PATH}/{user_id}", json=data)

    def delete_user(self, user_id: str) -> None:
        """Remove a hotspot user from the router."""
        self.client.delete(f"{self.USERS_PATH}/{user_id}")

    def enable_user(self, user_id: str) -> dict:
        """Enable a previously disabled hotspot user."""
        return self.client.patch(f"{self.USERS_PATH}/{user_id}", json={"disabled": "false"})

    def disable_user(self, user_id: str) -> dict:
        """Disable a hotspot user without deleting it."""
        return self.client.patch(f"{self.USERS_PATH}/{user_id}", json={"disabled": "true"})

    # ── Active Sessions ────────────────────────────────────────────────────────

    def list_active_sessions(self) -> list[dict]:
        """Return all currently active hotspot sessions."""
        return self.client.get(self.ACTIVE_PATH)

    def kick_session(self, session_id: str) -> None:
        """Forcefully disconnect an active hotspot session."""
        self.client.delete(f"{self.ACTIVE_PATH}/{session_id}")

    # ── Profiles ───────────────────────────────────────────────────────────────

    def list_profiles(self) -> list[dict]:
        """Return all hotspot user profiles."""
        return self.client.get(self.PROFILES_PATH)

    def get_profile(self, profile_id: str) -> dict:
        """Fetch a single hotspot user profile."""
        return self.client.get(f"{self.PROFILES_PATH}/{profile_id}")

    def create_profile(self, name: str, rate_limit: str = "", **kwargs: Any) -> dict:
        """Create a new hotspot user profile."""
        payload: dict[str, Any] = {"name": name, **kwargs}
        if rate_limit:
            payload["rate-limit"] = rate_limit
        return self.client.post(self.PROFILES_PATH, json=payload)
