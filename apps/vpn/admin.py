"""
Django admin configuration for the VPN application.
"""

from django.contrib import admin

from .models import VpnNode


@admin.register(VpnNode)
class VpnNodeAdmin(admin.ModelAdmin):
    list_display = ["name", "host", "port", "vpn_type", "is_active", "created_at"]
    list_filter = ["vpn_type", "is_active"]
    search_fields = ["name", "host", "description"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        ("General", {"fields": ("name", "description", "is_active")}),
        ("Network Endpoint", {"fields": ("host", "port", "vpn_type")}),
        ("Credentials", {"fields": ("public_certificate",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    ]
