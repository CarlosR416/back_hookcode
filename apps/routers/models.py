"""
Router models — MikroTik router and user-router associations.

Credentials are stored here. In production, consider using
a dedicated secrets manager (Vault, AWS Secrets Manager) instead of
storing passwords in the database.
"""

from django.conf import settings
from django.db import models


class Router(models.Model):
    """
    A registered MikroTik router.

    The API credentials stored here are used by the service layer
    to authenticate against the router's REST API.
    """

    name = models.CharField(max_length=100, verbose_name="Router name")
    host = models.GenericIPAddressField(default="0.0.0.0", verbose_name="IP address or hostname")
    port = models.PositiveIntegerField(unique=True, verbose_name="HTTPS port")

    # API credentials — use encrypted field or secrets manager in production
    api_username = models.CharField(max_length=100, unique=True, verbose_name="API username")
    api_password = models.CharField(max_length=255, unique=True, verbose_name="API password")

    ssl_verify = models.BooleanField(
        default=False,
        verbose_name="Verify SSL certificate",
        help_text="Set to True only when using a trusted CA-signed certificate.",
    )
    is_active = models.BooleanField(default=True, verbose_name="Active")
    description = models.TextField(blank=True, default="", verbose_name="Description")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    ROUTEROS_V6 = "v6"
    ROUTEROS_V7 = "v7"
    ROUTEROS_VERSION_CHOICES = [
        (ROUTEROS_V6, "RouterOS v6"),
        (ROUTEROS_V7, "RouterOS v7"),
    ]
    routeros_version = models.CharField(
        max_length=10,
        choices=ROUTEROS_VERSION_CHOICES,
        null=True,
        blank=True,
        default=None,
        verbose_name="RouterOS version",
    )

    class Meta:
        verbose_name = "Router"
        verbose_name_plural = "Routers"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.port:
            from .services import get_next_router_identifier
            self.port = get_next_router_identifier()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.host})"


class UserRouter(models.Model):
    """
    Association between a user and a router, including a role.

    Design notes (SOLID):
    - SRP: this model ONLY owns the user-router relationship + role.
      Router keeps connectivity data; User keeps auth data.
    - OCP: new roles can be added to RouterRole without touching Router or User.
    - LSP / ISP / DIP: consumers depend on this model via FK, not on concrete
      User or Router internals.

    Roles
    -----
    OWNER  — full CRUD + live actions on the router.
    VIEWER — read-only access (list, retrieve, ping).
    """

    class RouterRole(models.TextChoices):
        OWNER = "owner", "Owner"
        VIEWER = "viewer", "Viewer"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_routers",
        verbose_name="User",
    )
    router = models.ForeignKey(
        Router,
        on_delete=models.CASCADE,
        related_name="user_routers",
        verbose_name="Router",
    )
    role = models.CharField(
        max_length=20,
        choices=RouterRole.choices,
        default=RouterRole.VIEWER,
        verbose_name="Role",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "User Router"
        verbose_name_plural = "User Routers"
        # A user can only have one role per router
        constraints = [
            models.UniqueConstraint(fields=["user", "router"], name="unique_user_router")
        ]
        ordering = ["user", "router"]

    def __str__(self) -> str:
        return f"{self.user} → {self.router} [{self.role}]"
