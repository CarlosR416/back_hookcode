"""
Router model — represents a MikroTik router managed by the system.

Credentials are stored here. In production, consider using
a dedicated secrets manager (Vault, AWS Secrets Manager) instead of
storing passwords in the database.
"""

from django.db import models


class Router(models.Model):
    """
    A registered MikroTik router.

    The API credentials stored here are used by the service layer
    to authenticate against the router's REST API.
    """

    name = models.CharField(max_length=100, verbose_name="Router name")
    host = models.GenericIPAddressField(verbose_name="IP address or hostname")
    port = models.PositiveIntegerField(default=443, verbose_name="HTTPS port")

    # API credentials — use encrypted field or secrets manager in production
    api_username = models.CharField(max_length=100, verbose_name="API username")
    api_password = models.CharField(max_length=255, verbose_name="API password")

    ssl_verify = models.BooleanField(
        default=False,
        verbose_name="Verify SSL certificate",
        help_text="Set to True only when using a trusted CA-signed certificate.",
    )
    is_active = models.BooleanField(default=True, verbose_name="Active")
    description = models.TextField(blank=True, default="", verbose_name="Description")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Router"
        verbose_name_plural = "Routers"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.host})"
