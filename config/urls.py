"""
Root URL configuration for the WiFi Tickets API.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),

    # API endpoints
    path("api/auth/", include("apps.users.urls", namespace="auth")),
    path("api/routers/", include("apps.routers.urls", namespace="routers")),
    path("api/hotspot/", include("apps.hotspot.urls", namespace="hotspot")),
    path("api/tickets/", include("apps.tickets.urls", namespace="tickets")),

    # API Schema & Docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# Django Debug Toolbar — only active in development (when DEBUG=True)
if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
    except ImportError:
        pass
