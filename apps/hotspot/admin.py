"""
Admin registration for the hotspot application.
"""

from django.contrib import admin

from .models import HotspotProfile, HotspotTemplate, HotspotTemplateFile, HotspotUser


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


class HotspotTemplateFileInline(admin.TabularInline):
    """Inline for managing portal files from the template admin page."""

    model = HotspotTemplateFile
    extra = 1
    fields = ["filename", "role", "mime_type", "order"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["order", "filename"]
    show_change_link = True  # link to the full file edit page


@admin.register(HotspotTemplate)
class HotspotTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "vendor", "is_active", "created_by", "created_at"]
    list_filter = ["vendor", "is_active"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_by", "created_at", "updated_at"]
    inlines = [HotspotTemplateFileInline]

    def save_model(self, request, obj, form, change):
        if not change:  # only on creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(HotspotTemplateFile)
class HotspotTemplateFileAdmin(admin.ModelAdmin):
    list_display = ["filename", "template", "role", "mime_type", "order", "updated_at"]
    list_filter = ["template", "role"]
    search_fields = ["filename", "template__name"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["template", "order", "filename"]
