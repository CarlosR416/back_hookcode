"""
Ticket model — a single-use WiFi access code.
"""

import uuid

from django.db import models

from apps.routers.models import Router


class Ticket(models.Model):
    """
    A single WiFi access ticket.

    Tickets can be generated in batches, printed, and handed to customers.
    When a ticket is activated, a corresponding hotspot user is created on
    the router with the configured profile and duration.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"       # Generated, not yet used
        ACTIVE = "active", "Active"          # Hotspot user created on router
        EXPIRED = "expired", "Expired"       # Session time exhausted or manually expired
        CANCELLED = "cancelled", "Cancelled" # Voided before use

    router = models.ForeignKey(
        Router,
        on_delete=models.CASCADE,
        related_name="tickets",
        verbose_name="Router",
    )
    code = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name="Ticket code",
    )
    profile_name = models.CharField(
        max_length=100,
        verbose_name="Hotspot profile",
        help_text="Name of the MikroTik hotspot user profile to assign.",
    )
    duration_minutes = models.PositiveIntegerField(
        default=60,
        verbose_name="Duration (minutes)",
        help_text="Session duration that will be applied as limit-uptime on the router.",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="Status",
    )
    mk_user_id = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="MikroTik user ID",
        help_text="RouterOS *.id of the created hotspot user, set on activation.",
    )
    activated_at = models.DateTimeField(null=True, blank=True, verbose_name="Activated at")
    comment = models.TextField(blank=True, default="", verbose_name="Comment")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Ticket {str(self.code)[:8]}… [{self.status}]"
