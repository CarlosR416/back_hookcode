from django.db import models
from django.utils import timezone
from jinja2 import Template
from apps.routers.models import Router

class ScriptTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Template name")
    description = models.TextField(blank=True, verbose_name="Description")
    content = models.TextField(verbose_name="Script content (Jinja2)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Script Template"
        verbose_name_plural = "Script Templates"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class RouterScriptExecution(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("IN_PROGRESS", "In Progress"),
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
    ]

    router = models.ForeignKey(
        Router, on_delete=models.CASCADE, related_name="script_executions"
    )
    template = models.ForeignKey(
        ScriptTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )
    variables_used = models.JSONField(default=dict, verbose_name="Variables used")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="PENDING"
    )
    output_log = models.TextField(blank=True, verbose_name="Execution output")
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Script Execution"
        verbose_name_plural = "Script Executions"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.router.name} - {self.template.name if self.template else 'Ad-hoc'} ({self.status})"

    def mark_completed(self, status: str, output: str = "") -> None:
        self.status = status
        self.output_log = output
        self.completed_at = timezone.now()
        self.save()

    @property
    def rendered_content(self) -> str:
        """
        Renders the script content using Jinja2 with the variables provided.
        """
        if not self.template:
            return ""
        
        template = Template(self.template.content)
        return template.render(**self.variables_used)


class ScriptDownloadToken(models.Model):
    """
    Cryptographically secure, single-use download token (Burn-on-Read)
    for provisioning RouterOS scripts on remote MikroTik devices.
    """

    router = models.ForeignKey(
        Router,
        on_delete=models.CASCADE,
        related_name="download_tokens",
        verbose_name="Router",
    )
    template = models.ForeignKey(
        ScriptTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="download_tokens",
        verbose_name="Script Template",
    )
    execution = models.ForeignKey(
        RouterScriptExecution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="download_tokens",
        verbose_name="Script Execution",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True, verbose_name="Token")
    variables_used = models.JSONField(default=dict, blank=True, verbose_name="Variables used")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created at")
    expires_at = models.DateTimeField(verbose_name="Expires at")
    is_consumed = models.BooleanField(default=False, verbose_name="Is consumed")
    consumed_at = models.DateTimeField(null=True, blank=True, verbose_name="Consumed at")
    include_cleanup = models.BooleanField(
        default=True,
        verbose_name="Include self-cleanup",
        help_text="Appends command to remove the .rsc file from router storage after import.",
    )
    filename = models.CharField(
        max_length=100,
        default="setup.rsc",
        verbose_name="Destination file name",
    )

    class Meta:
        verbose_name = "Script Download Token"
        verbose_name_plural = "Script Download Tokens"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["router", "-created_at"]),
        ]

    def is_valid(self) -> bool:
        """Check if the token has not been consumed and has not expired."""
        return not self.is_consumed and timezone.now() <= self.expires_at

    def burn(self) -> None:
        """Consume the token immediately to prevent reuse (Burn-on-Read)."""
        self.is_consumed = True
        self.consumed_at = timezone.now()
        self.save(update_fields=["is_consumed", "consumed_at"])

    @property
    def rendered_content(self) -> str:
        """Render script using linked execution or template + variables."""
        if self.execution:
            content = self.execution.rendered_content
        elif self.template:
            template = Template(self.template.content)
            content = template.render(**self.variables_used)
        else:
            content = self.variables_used.get("custom_script", "")

        banner = (
            f"# ====================================================================\n"
            f"# WiFi Tickets - Automated RouterOS Provisioning Script\n"
            f"# Router: {self.router.name} ({self.router.host})\n"
            f"# Single-use token. Burned upon download.\n"
            f"# ====================================================================\n\n"
        )

        output = banner + content

        if self.include_cleanup:
            cleanup_script = (
                f"\n\n# --- Self-cleanup from router storage ---\n"
                f":delay 2s;\n"
                f"/file remove [find name=\"{self.filename}\"];\n"
                f":log info \"WiFi Tickets script executed and removed from storage.\";\n"
            )
            output += cleanup_script

        return output

    def __str__(self) -> str:
        return f"Token for {self.router.name} (Consumed: {self.is_consumed})"
