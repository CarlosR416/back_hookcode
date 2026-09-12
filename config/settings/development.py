"""
Development settings — extends base settings with debug tools.
"""

from .base import *  # noqa: F401, F403

DEBUG = config("DEBUG", default=True, cast=bool)

# Allow all hosts locally by default
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*", cast=Csv()) if config("ALLOWED_HOSTS", default="") else ["*"]

# CORS — allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True

# Django Debug Toolbar
INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]  # noqa: F405
INTERNAL_IPS = ["127.0.0.1"]

# Use console email backend during development unless valid Brevo SMTP credentials are provided
if not EMAIL_HOST_USER or "your-brevo" in EMAIL_HOST_USER:  # noqa: F405
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
