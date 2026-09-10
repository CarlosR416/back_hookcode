"""
URL configuration for the VPN application.
"""

from rest_framework.routers import DefaultRouter

from .views import VpnNodeViewSet

app_name = "vpn"

router = DefaultRouter()
router.register(r"nodes", VpnNodeViewSet, basename="nodes")

urlpatterns = router.urls
