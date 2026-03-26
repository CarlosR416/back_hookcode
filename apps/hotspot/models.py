"""
Hotspot models — HotspotProfile, HotspotUser, and portal templates.

HotspotProfile / HotspotUser mirror MikroTik data locally for audit/reports.
HotspotTemplate / HotspotTemplateFile store per-vendor portal HTML templates
that can be previewed in the browser OR downloaded as a ready-to-upload package.
"""

from django.conf import settings
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


# ---------------------------------------------------------------------------
# Hotspot portal templates
# ---------------------------------------------------------------------------


class HotspotTemplate(models.Model):
    """
    A reusable portal template for a captive-portal / hotspot device.

    Design goals (SOLID)
    --------------------
    SRP  — this model stores template *metadata* only. File content lives in
           HotspotTemplateFile. Rendering logic lives in the service layer.
    OCP  — adding support for a new vendor (Cisco, Ubiquiti…) means adding
           a new choice to `Vendor` and a new renderer; no existing code changes.
    DIP  — views/API depend on this model, not on vendor-specific details.

    Vendor context
    --------------
    MikroTik hotspot portals are a folder of static HTML/CSS/JS files uploaded
    to the router's /flash/hotspot/ directory. The variables available at render
    time (e.g. $(username), $(link-login)) differ per vendor; the `variables`
    JSONField documents the expected context for this template.
    """

    class Vendor(models.TextChoices):
        MIKROTIK = "mikrotik", "MikroTik"
        # Future vendors — uncomment to enable:
        # CISCO = "cisco", "Cisco"
        # UBIQUITI = "ubiquiti", "Ubiquiti"

    name = models.CharField(max_length=150, unique=True, verbose_name="Template name")
    description = models.TextField(blank=True, default="", verbose_name="Description")

    vendor = models.CharField(
        max_length=30,
        choices=Vendor.choices,
        default=Vendor.MIKROTIK,
        verbose_name="Target vendor",
        help_text="Device type this template is designed for.",
    )

    # Free-form metadata: logo URL, primary color, company name, etc.
    # The renderer merges this dict with any per-request overrides.
    variables = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Default template variables",
        help_text=(
            "Key-value pairs injected into the Jinja2 context when rendering. "
            "Example: {\"company\": \"MyWifi\", \"primary_color\": \"#4f46e5\"}"
        ),
    )

    # Soft ownership — who created this template
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="hotspot_templates",
        verbose_name="Created by",
    )

    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Hotspot Template"
        verbose_name_plural = "Hotspot Templates"
        ordering = ["vendor", "name"]

    def __str__(self) -> str:
        return f"[{self.get_vendor_display()}] {self.name}"


class HotspotTemplateFile(models.Model):
    """
    A single file that belongs to a HotspotTemplate.

    For MikroTik the minimum set is:
        login.html       — the main login form
        alogin.html      — redirect page after authentication
        error.html       — error / 'wrong password' page
        status.html      — session status page (optional)
        logout.html      — logout confirmation page (optional)

    The `content` field stores raw Jinja2 source.

    Two rendering modes (resolved in the service layer, not here):
        preview  — injects browser-friendly context (absolute URLs for assets,
                   dummy values for vendor variables like $(username)).
        download — produces the file as-is for deployment on the device.

    SRP: this model knows nothing about how rendering is done. The renderer
    service reads `content` and returns the result.
    """

    class FileRole(models.TextChoices):
        LOGIN = "login", "Login page"
        ALOGIN = "alogin", "After-login redirect"
        ERROR = "error", "Error page"
        STATUS = "status", "Session status"
        LOGOUT = "logout", "Logout page"
        ASSET = "asset", "Static asset (CSS / JS / image)"
        OTHER = "other", "Other"

    template = models.ForeignKey(
        HotspotTemplate,
        on_delete=models.CASCADE,
        related_name="files",
        verbose_name="Parent template",
    )

    # The filename as it will appear on the device, e.g. "login.html", "style.css"
    filename = models.CharField(
        max_length=255,
        verbose_name="File name",
        help_text="Name of the file as uploaded to the device, e.g. 'login.html'.",
    )

    role = models.CharField(
        max_length=20,
        choices=FileRole.choices,
        default=FileRole.OTHER,
        verbose_name="File role",
        help_text="Semantic role within the portal for UI hints and validation.",
    )

    # Raw Jinja2 source — may include vendor-specific variables AND template vars
    content = models.TextField(verbose_name="File content (Jinja2)")

    # MIME type stored explicitly so the download endpoint can set Content-Type
    mime_type = models.CharField(
        max_length=100,
        default="text/html",
        verbose_name="MIME type",
        help_text="e.g. 'text/html', 'text/css', 'application/javascript'.",
    )

    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Display order",
        help_text="Lower number appears first in the UI.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Hotspot Template File"
        verbose_name_plural = "Hotspot Template Files"
        # Each filename must be unique within a template
        constraints = [
            models.UniqueConstraint(
                fields=["template", "filename"],
                name="unique_template_filename",
            )
        ]
        ordering = ["template", "order", "filename"]

    def __str__(self) -> str:
        return f"{self.template.name} / {self.filename}"
