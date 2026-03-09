"""
URL configuration for the hotspot application.
"""

from rest_framework.routers import DefaultRouter

from .views import HotspotProfileViewSet, HotspotUserViewSet

app_name = "hotspot"

router = DefaultRouter()
router.register("profiles", HotspotProfileViewSet, basename="hotspot-profiles")
router.register("users", HotspotUserViewSet, basename="hotspot-users")

urlpatterns = router.urls
