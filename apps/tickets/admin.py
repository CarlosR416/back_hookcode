"""
Admin registration for the tickets application.
"""

from django.contrib import admin

from .models import Ticket


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ["short_code", "router", "profile_name", "duration_minutes", "status", "activated_at", "created_at"]
    list_filter = ["router", "status", "profile_name"]
    search_fields = ["code", "comment"]
    readonly_fields = ["code", "mk_user_id", "activated_at", "created_at", "updated_at"]

    def short_code(self, obj) -> str:
        return str(obj.code)[:12] + "…"

    short_code.short_description = "Code"
