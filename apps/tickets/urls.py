"""
URL configuration for the tickets application.
"""

from rest_framework.routers import DefaultRouter

from .views import TicketViewSet

app_name = "tickets"

router = DefaultRouter()
router.register("", TicketViewSet, basename="tickets")

urlpatterns = router.urls
