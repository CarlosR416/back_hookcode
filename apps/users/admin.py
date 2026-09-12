"""
Admin registration for the users application.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import EmailVerificationCode, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom user admin with email as the primary identifier."""

    list_display = ["email", "username", "first_name", "last_name", "is_staff", "is_active", "is_email_verified"]
    search_fields = ["email", "username", "first_name", "last_name"]
    ordering = ["email"]
    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_email_verified",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "password1", "password2"),
            },
        ),
    )


@admin.register(EmailVerificationCode)
class EmailVerificationCodeAdmin(admin.ModelAdmin):
    """Admin inspection for OTP email verification codes."""

    list_display = ["user", "code", "created_at", "expires_at", "attempts", "is_used"]
    list_filter = ["is_used", "created_at"]
    search_fields = ["user__email", "code"]
    readonly_fields = ["created_at"]
