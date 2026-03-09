"""
Admin registration for the routers application.
"""

from django.contrib import admin

from .models import Router


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
