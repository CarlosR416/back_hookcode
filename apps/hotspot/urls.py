"""
URL configuration for the hotspot application.
"""

from rest_framework.routers import DefaultRouter

from .views import (
    HotspotProfileViewSet,
    HotspotTemplateFileViewSet,
    HotspotTemplateViewSet,
    HotspotUserViewSet,
)

app_name = "hotspot"

router = DefaultRouter()
router.register("profiles", HotspotProfileViewSet, basename="hotspot-profiles")
router.register("users", HotspotUserViewSet, basename="hotspot-users")
router.register("templates", HotspotTemplateViewSet, basename="hotspot-templates")
router.register("template-files", HotspotTemplateFileViewSet, basename="hotspot-template-files")

urlpatterns = router.urls
