"""
AppConfig for the users application.
"""

from django.apps import AppConfig
from django.conf import settings
import firebase_admin
from firebase_admin import credentials


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    verbose_name = "Users"

    def ready(self):
        """Initialize Firebase Admin SDK on application startup."""
        if getattr(settings, "FIREBASE_CREDENTIALS_PATH", None) and not firebase_admin._apps:
            try:
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                firebase_admin.initialize_app(cred)
            except Exception as e:
                print(f"Failed to initialize Firebase app: {e}")
