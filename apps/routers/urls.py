"""
URL configuration for the routers application.
"""

from rest_framework.routers import DefaultRouter

from .views import RouterViewSet, UserRouterViewSet

app_name = "routers"

router = DefaultRouter()
router.register("memberships", UserRouterViewSet, basename="router-memberships")
router.register("", RouterViewSet, basename="routers")

urlpatterns = router.urls
