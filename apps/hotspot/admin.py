"""
Admin registration for the hotspot application.
"""

from django.contrib import admin

from .models import HotspotProfile, HotspotUser


@admin.register(HotspotProfile)
class HotspotProfileAdmin(admin.ModelAdmin):
    list_display = ["name", "router", "rate_limit", "session_timeout", "shared_users"]
    list_filter = ["router"]
    search_fields = ["name"]
    readonly_fields = ["mk_id", "created_at", "updated_at"]


@admin.register(HotspotUser)
class HotspotUserAdmin(admin.ModelAdmin):
    list_display = ["username", "router", "profile", "is_disabled", "created_at"]
    list_filter = ["router", "is_disabled"]
    search_fields = ["username", "comment"]
    readonly_fields = ["mk_id", "created_at", "updated_at"]
