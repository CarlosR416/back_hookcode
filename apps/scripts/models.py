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
