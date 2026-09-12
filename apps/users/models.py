"""
Custom User model for the WiFi Tickets application.

Extends AbstractUser to allow future profile fields without painful migrations.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model.
    Uses email as the unique login identifier instead of username.
    """

    email = models.EmailField(unique=True, verbose_name="Email address")
    is_email_verified = models.BooleanField(
        default=False,
        verbose_name="Is email verified",
        help_text="Designates whether this user has verified their email address.",
    )

    # Make email the login field
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]  # username still required for admin compatibility

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email


class EmailVerificationCode(models.Model):
    """
    6-digit numeric OTP code for user email verification.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="verification_codes",
        verbose_name="User",
    )
    code = models.CharField(max_length=6, verbose_name="OTP Code")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created at")
    expires_at = models.DateTimeField(verbose_name="Expires at")
    attempts = models.PositiveIntegerField(default=0, verbose_name="Failed attempts")
    is_used = models.BooleanField(default=False, verbose_name="Is used")

    class Meta:
        verbose_name = "Email Verification Code"
        verbose_name_plural = "Email Verification Codes"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["code"]),
        ]

    def is_expired(self) -> bool:
        """Check if the OTP code has passed its expiration timestamp."""
        from django.utils import timezone
        return timezone.now() >= self.expires_at

    def can_attempt(self, max_attempts: int = 5) -> bool:
        """Check if further verification attempts are permitted."""
        return self.attempts < max_attempts and not self.is_used and not self.is_expired()

    def __str__(self) -> str:
        return f"OTP for {self.user.email} (Used: {self.is_used})"
