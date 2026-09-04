"""
Admin registration for the routers application.
"""

from django.contrib import admin

from .models import Router, UserRouter


@admin.register(Router)
class RouterAdmin(admin.ModelAdmin):
    list_display = ["name", "host", "port", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "host"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        ("Connection", {"fields": ("name", "host", "port", "ssl_verify", "is_active")}),
        ("Credentials", {"fields": ("api_username", "api_password"), "classes": ("collapse",)}),
        ("Metadata", {"fields": ("description", "created_at", "updated_at")}),
    )


class UserRouterInline(admin.TabularInline):
    """Inline for managing user-router memberships from the Router admin page."""

    model = UserRouter
    extra = 1
    autocomplete_fields = ["user"]
    fields = ["user", "role", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(UserRouter)
class UserRouterAdmin(admin.ModelAdmin):
    list_display = ["user", "router", "role", "created_at"]
    list_filter = ["role"]
    search_fields = ["user__email", "router__name"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["user", "router"]
