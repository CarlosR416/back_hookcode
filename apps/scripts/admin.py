from django.contrib import admin

from .models import RouterScriptExecution, ScriptDownloadToken, ScriptTemplate

# Register your models here.
class ScriptTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'content')
    list_filter = ('name', 'description')
    search_fields = ('name', 'description')
    ordering = ('name',)

class RouterScriptExecutionAdmin(admin.ModelAdmin):
    list_display = ('router', 'template', 'status', 'created_at', 'completed_at')
    list_filter = ('router', 'template', 'status')
    search_fields = ('router', 'template', 'status')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'completed_at')


class ScriptDownloadTokenAdmin(admin.ModelAdmin):
    list_display = ('router', 'token', 'is_consumed', 'expires_at', 'created_at')
    list_filter = ('is_consumed', 'created_at')
    search_fields = ('router__name', 'token')
    readonly_fields = ('token', 'created_at', 'consumed_at')


admin.site.register(ScriptTemplate, ScriptTemplateAdmin)
admin.site.register(RouterScriptExecution, RouterScriptExecutionAdmin)
admin.site.register(ScriptDownloadToken, ScriptDownloadTokenAdmin)
