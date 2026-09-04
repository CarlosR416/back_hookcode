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

    # Make email the login field
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]  # username still required for admin compatibility

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email
