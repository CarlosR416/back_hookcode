"""
Development settings — extends base settings with debug tools.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

# Allow all hosts locally
ALLOWED_HOSTS = ["*"]

# Django Debug Toolbar
INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]  # noqa: F405
INTERNAL_IPS = ["127.0.0.1"]

# Use console email backend during development unless Brevo SMTP credentials are provided
if not EMAIL_HOST_USER:  # noqa: F405
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
