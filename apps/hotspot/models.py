"""
Hotspot models — HotspotProfile and HotspotUser.

These models mirror the relevant data from MikroTik on the Django side,
so reports and audits can be run locally without repeated API calls.
"""

from django.db import models

from apps.routers.models import Router


class HotspotProfile(models.Model):
    """
    A MikroTik hotspot user profile (bandwidth / session limits).
    Mirrors ip/hotspot/user/profile on the router.
    """

    router = models.ForeignKey(
        Router,
        on_delete=models.CASCADE,
        related_name="hotspot_profiles",
        verbose_name="Router",
    )
    mk_id = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="MikroTik ID",
        help_text="The *.id returned by the RouterOS API, e.g. *1.",
    )
    name = models.CharField(max_length=100, verbose_name="Profile name")
    rate_limit = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Rate limit",
        help_text="MikroTik rate-limit string, e.g. '2M/2M'.",
    )
    session_timeout = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="Session timeout",
        help_text="RouterOS time string, e.g. '1h30m'.",
    )
    shared_users = models.PositiveIntegerField(
        default=1, verbose_name="Max simultaneous sessions"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Hotspot Profile"
        verbose_name_plural = "Hotspot Profiles"
        unique_together = [("router", "name")]
        ordering = ["router", "name"]

    def __str__(self) -> str:
        return f"{self.name} [{self.router.name}]"


class HotspotUser(models.Model):
    """
    A MikroTik hotspot user account.
    Mirrors ip/hotspot/user on the router.
    """

    router = models.ForeignKey(
        Router,
        on_delete=models.CASCADE,
        related_name="hotspot_users",
        verbose_name="Router",
    )
    profile = models.ForeignKey(
        HotspotProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="Profile",
    )
    mk_id = models.CharField(max_length=50, blank=True, default="", verbose_name="MikroTik ID")
    username = models.CharField(max_length=100, verbose_name="Username")
    comment = models.TextField(blank=True, default="", verbose_name="Comment")
    is_disabled = models.BooleanField(default=False, verbose_name="Disabled on router")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Hotspot User"
        verbose_name_plural = "Hotspot Users"
        unique_together = [("router", "username")]
        ordering = ["router", "username"]

    def __str__(self) -> str:
        return f"{self.username} [{self.router.name}]"
