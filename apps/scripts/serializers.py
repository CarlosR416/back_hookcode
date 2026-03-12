from rest_framework import serializers
from .models import ScriptTemplate, RouterScriptExecution

class ScriptTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScriptTemplate
        fields = ["id", "name", "description", "content", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class RouterScriptExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RouterScriptExecution
        fields = [
            "id",
            "router",
            "template",
            "variables_used",
            "rendered_content",
            "status",
            "output_log",
            "created_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "rendered_content",
            "status",
            "output_log",
            "created_at",
            "completed_at",
        ]
