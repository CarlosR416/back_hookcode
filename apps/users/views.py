"""
Views for the users application.
"""

from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema

from core.responses import created_response, error_response, success_response

from .serializers import ChangePasswordSerializer, RegisterSerializer, UserSerializer, GoogleLoginSerializer

User = get_user_model()


class UserViewSet(GenericViewSet):
    """
    ViewSet for user account management.

    Endpoints:
        POST   /api/auth/register/        — public, create account
        GET    /api/auth/me/              — return own profile
        PUT    /api/auth/me/              — update own profile
        POST   /api/auth/me/change-password/ — change password
    """

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action == "register":
            return [AllowAny()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "register":
            return RegisterSerializer
        if self.action == "change_password":
            return ChangePasswordSerializer
        return UserSerializer

    @action(detail=False, methods=["post"], url_path="register")
    def register(self, request: Request) -> Response:
        """Create a new user account."""
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return created_response(UserSerializer(user).data)

    @action(detail=False, methods=["get", "put", "patch"], url_path="me")
    def me(self, request: Request) -> Response:
        """Retrieve or update the authenticated user's own profile."""
        if request.method == "GET":
            serializer = UserSerializer(request.user)
            return success_response(serializer.data)

        serializer = UserSerializer(
            request.user, data=request.data, partial=(request.method == "PATCH")
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(serializer.data)

    @action(detail=False, methods=["post"], url_path="me/change-password")
    def change_password(self, request: Request) -> Response:
        """Change the authenticated user's password."""
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return error_response(
                detail=_("Old password is incorrect."),
                code="wrong_password",
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return success_response({"detail": _("Password updated successfully.")})

    @extend_schema(
        request=GoogleLoginSerializer,
        responses={200: UserSerializer},
        tags=["auth"]
    )
    @action(detail=False, methods=["post"], url_path="google", permission_classes=[AllowAny])
    def google(self, request: Request) -> Response:
        """Authenticate using a Firebase ID token from Google Sign-in."""
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        decoded_token = serializer.validated_data["firebase_token"]
        email = decoded_token.get("email")
        uid = decoded_token.get("uid")

        if not email:
            return error_response(
                detail=_("Email is missing from the Google token."),
                code="missing_email",
                status=status.HTTP_400_BAD_REQUEST,
            )

        user, created = User.objects.get_or_create(email=email)
        
        if created:
            if uid:
                user.username = uid
            user.set_unusable_password()
            user.save()

        refresh = RefreshToken.for_user(user)

        return success_response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
            "is_new_user": created,
        })
