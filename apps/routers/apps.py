"""
AppConfig for the routers application.
"""

from django.apps import AppConfig


class RoutersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.routers"
    verbose_name = "Routers"
