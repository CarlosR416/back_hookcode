from django.contrib import admin

from .models import ScriptTemplate, RouterScriptExecution

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
    

admin.site.register(ScriptTemplate, ScriptTemplateAdmin)
admin.site.register(RouterScriptExecution, RouterScriptExecutionAdmin)
