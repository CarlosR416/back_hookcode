"""
URL configuration for the users application.

JWT token endpoints are provided by rest_framework_simplejwt.
Custom endpoints are routed through the UserViewSet.
"""

from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from .views import UserViewSet

app_name = "auth"

# Register ViewSet routes
router = DefaultRouter()
router.register("", UserViewSet, basename="users")

urlpatterns = [
    # JWT endpoints
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    # User account routes from ViewSet
    *router.urls,
]
