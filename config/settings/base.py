"""
Django base settings shared across all environments.
"""

from datetime import timedelta
from pathlib import Path
import sys

from decouple import Csv, config
from django.utils.translation import gettext_lazy as _

# ── Paths ───────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ── Security ────────────────────────────────────────────────────────────────────
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost", cast=Csv())


# ── Application definition ──────────────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.users",
    "apps.routers",
    "apps.hotspot",
    "apps.tickets",
    "apps.scripts",
    "apps.radius",
    "apps.vpn",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


# ── Middleware ──────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ── Database ────────────────────────────────────────────────────────────────────
DB_CONN_MAX_AGE = config("DB_CONN_MAX_AGE", default=60, cast=int)

DATABASES = {
    "default": {
        "ENGINE": config("DB_ENGINE", default="django.db.backends.postgresql"),
        "NAME": config("DB_NAME", default="wifitickets"),
        "USER": config("DB_USER", default="wifitickets_user"),
        "PASSWORD": config("DB_PASSWORD", default="wifitickets_pass"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
        "CONN_MAX_AGE": DB_CONN_MAX_AGE,
    },
    "radius": {
        "ENGINE": config("RADIUS_DB_ENGINE", default=config("DB_ENGINE", default="django.db.backends.postgresql")),
        "NAME": config("RADIUS_DB_NAME", default=config("DB_NAME", default="wifitickets")),
        "USER": config("RADIUS_DB_USER", default=config("DB_USER", default="wifitickets_user")),
        "PASSWORD": config("RADIUS_DB_PASSWORD", default=config("DB_PASSWORD", default="wifitickets_pass")),
        "HOST": config("RADIUS_DB_HOST", default=config("DB_HOST", default="localhost")),
        "PORT": config("RADIUS_DB_PORT", default=config("DB_PORT", default="5432")),
        "CONN_MAX_AGE": DB_CONN_MAX_AGE,
    },
}

DATABASE_ROUTERS = [
    "apps.radius.routers.RadiusDatabaseRouter",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ── Custom user model ───────────────────────────────────────────────────────────
AUTH_USER_MODEL = "users.User"


# ── Password validation ─────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Fast password hasher and in-memory email backend for test runs only
if "test" in sys.argv:
    PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    # In tests, radius uses the local default database configuration instead of the external server
    DATABASES["radius"] = {
        **DATABASES["default"],
        "TEST": {"NAME": "test_radius"},
    }


# ── Internationalisation ────────────────────────────────────────────────────────
LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", _("English")),
    ("es", _("Spanish")),
]
LOCALE_PATHS = [
    BASE_DIR / "locale",
]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# ── Static files ────────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


# ── Django REST Framework ───────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardResultsPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
}


# ── JWT ─────────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=config("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=60, cast=int)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=config("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7, cast=int)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}


# ── CORS & CSRF ──────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000",
    cast=Csv(),
)
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="",
    cast=Csv(),
)


# ── API Docs (drf-spectacular) ──────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "WiFi Tickets API",
    "DESCRIPTION": "Backend API for MikroTik router and WiFi ticket management.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}


# ── MikroTik defaults ───────────────────────────────────────────────────────────
MIKROTIK_DEFAULT_PORT = config("MIKROTIK_DEFAULT_PORT", default=443, cast=int)
MIKROTIK_SSL_VERIFY = config("MIKROTIK_SSL_VERIFY", default=False, cast=bool)


# ── Firebase ────────────────────────────────────────────────────────────────────
FIREBASE_CREDENTIALS_PATH = config("FIREBASE_CREDENTIALS_PATH", default="")


# ── Email & Brevo SMTP Relay ──────────────────────────────────────────────────
EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = config("EMAIL_HOST", default="smtp-relay.brevo.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="WiFi Tickets <noreply@wifitickets.com>")
EMAIL_OTP_EXPIRATION_MINUTES = config("EMAIL_OTP_EXPIRATION_MINUTES", default=5, cast=int)
EMAIL_OTP_RESEND_COOLDOWN_SECONDS = config("EMAIL_OTP_RESEND_COOLDOWN_SECONDS", default=60, cast=int)

# ── RouterOS Script Provisioning ──────────────────────────────────────────────
SCRIPT_TOKEN_EXPIRATION_MINUTES = config("SCRIPT_TOKEN_EXPIRATION_MINUTES", default=10, cast=int)
