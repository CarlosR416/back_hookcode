from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from .models import RouterScriptExecution, ScriptDownloadToken, ScriptTemplate

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


class GenerateBootstrapTokenSerializer(serializers.Serializer):
    """Input serializer for generating a single-use script download token."""

    template = serializers.PrimaryKeyRelatedField(
        queryset=ScriptTemplate.objects.all(),
        required=False,
        allow_null=True,
        help_text=_("Optional template to render."),
    )
    variables = serializers.JSONField(
        required=False,
        default=dict,
        help_text=_("Variables to interpolate into the Jinja2 template."),
    )
    expiration_minutes = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=60,
        default=10,
        help_text=_("Token expiration in minutes (default 10)."),
    )
    include_cleanup = serializers.BooleanField(
        required=False,
        default=True,
        help_text=_("Whether to append self-destruction command (/file remove) to the script."),
    )
    filename = serializers.CharField(
        required=False,
        default="setup.rsc",
        max_length=100,
        help_text=_("Destination filename on the MikroTik router."),
    )


class ScriptDownloadTokenResponseSerializer(serializers.Serializer):
    """Output serializer returning the generated token and ready-to-run RouterOS command."""

    token = serializers.CharField()
    download_url = serializers.CharField()
    routeros_command = serializers.CharField()
    expires_at = serializers.DateTimeField()
