"""
Views for the users application.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema

from core.responses import created_response, error_response, success_response

from .models import EmailVerificationCode
from .serializers import (
    ChangePasswordSerializer,
    GoogleLoginSerializer,
    RegisterSerializer,
    ResendOTPSerializer,
    UserSerializer,
    VerifyOTPSerializer,
)

User = get_user_model()


class UserViewSet(GenericViewSet):
    """
    ViewSet for user account management.

    Endpoints:
        POST   /api/auth/register/            — public, create unverified account
        POST   /api/auth/verify-otp/          — public, verify email with 6-digit OTP
        POST   /api/auth/resend-otp/          — public, resend OTP code
        GET    /api/auth/me/                  — return own profile
        PUT    /api/auth/me/                  — update own profile
        POST   /api/auth/me/change-password/  — change password
        POST   /api/auth/google/              — Google Sign-in / Firebase
    """

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ["register", "verify_otp", "resend_otp"]:
            return [AllowAny()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "register":
            return RegisterSerializer
        if self.action == "verify_otp":
            return VerifyOTPSerializer
        if self.action == "resend_otp":
            return ResendOTPSerializer
        if self.action == "change_password":
            return ChangePasswordSerializer
        if self.action == "google":
            return GoogleLoginSerializer
        return UserSerializer

    @extend_schema(
        request=RegisterSerializer,
        responses={201: UserSerializer},
        tags=["auth"],
    )
    @action(detail=False, methods=["post"], url_path="register")
    def register(self, request: Request) -> Response:
        """Create a new unverified user account and dispatch 6-digit OTP verification email."""
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return created_response(
            {
                **UserSerializer(user).data,
                "message": _("Account registered. Please enter the 6-digit OTP code sent to %(email)s.")
                % {"email": user.email},
            }
        )

    @extend_schema(
        request=VerifyOTPSerializer,
        responses={200: OpenApiTypes.OBJECT},
        tags=["auth"],
    )
    @action(detail=False, methods=["post"], url_path="verify-otp", permission_classes=[AllowAny])
    def verify_otp(self, request: Request) -> Response:
        """Verify user account with a 6-digit OTP code and issue JWT tokens upon success."""
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return error_response(
                detail=_("No account found with the provided email address."),
                code="user_not_found",
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.is_email_verified:
            return error_response(
                detail=_("This account's email is already verified."),
                code="already_verified",
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Retrieve the latest active OTP code
        otp_record = (
            EmailVerificationCode.objects.filter(user=user, is_used=False)
            .order_by("-created_at")
            .first()
        )

        if not otp_record or otp_record.is_expired():
            return error_response(
                detail=_("The verification code has expired. Please request a new one."),
                code="expired_otp",
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not otp_record.can_attempt():
            return error_response(
                detail=_("Maximum verification attempts exceeded. Please request a new code."),
                code="too_many_attempts",
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp_record.code != otp:
            otp_record.attempts += 1
            otp_record.save(update_fields=["attempts"])
            remaining = max(0, 5 - otp_record.attempts)
            return error_response(
                detail=_("Invalid verification code. %(remaining)d attempts remaining.")
                % {"remaining": remaining},
                code="invalid_otp",
                status=status.HTTP_400_BAD_REQUEST,
            )

        # OTP is valid: mark code as used and activate the user
        otp_record.is_used = True
        otp_record.save(update_fields=["is_used"])

        user.is_email_verified = True
        user.is_active = True
        user.save(update_fields=["is_email_verified", "is_active"])

        refresh = RefreshToken.for_user(user)

        return success_response(
            {
                "detail": _("Email verified successfully."),
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            }
        )

    @extend_schema(
        request=ResendOTPSerializer,
        responses={200: OpenApiTypes.OBJECT},
        tags=["auth"],
    )
    @action(detail=False, methods=["post"], url_path="resend-otp", permission_classes=[AllowAny])
    def resend_otp(self, request: Request) -> Response:
        """Resend a fresh 6-digit OTP code to the user's email if the account is unverified."""
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Return generic success to prevent email enumeration
            return success_response(
                {"detail": _("If an unverified account exists, a new verification code has been sent.")}
            )

        if user.is_email_verified:
            return error_response(
                detail=_("This account's email is already verified."),
                code="already_verified",
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Enforce cooldown to protect Brevo SMTP quota
        cooldown_seconds = getattr(settings, "EMAIL_OTP_RESEND_COOLDOWN_SECONDS", 60)
        latest_otp = (
            EmailVerificationCode.objects.filter(user=user)
            .order_by("-created_at")
            .first()
        )
        if latest_otp:
            time_since_creation = (timezone.now() - latest_otp.created_at).total_seconds()
            if time_since_creation < cooldown_seconds:
                remaining_wait = int(cooldown_seconds - time_since_creation)
                return error_response(
                    detail=_("Please wait %(seconds)d seconds before requesting another code.")
                    % {"seconds": remaining_wait},
                    code="resend_cooldown",
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

        from .emails import generate_and_send_otp

        generate_and_send_otp(user)

        return success_response(
            {"detail": _("A new verification code has been sent to your email.")}
        )

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
            user.is_email_verified = True
            user.is_active = True
            user.set_unusable_password()
            user.save()
        elif not user.is_email_verified:
            user.is_email_verified = True
            user.is_active = True
            user.save(update_fields=["is_email_verified", "is_active"])

        refresh = RefreshToken.for_user(user)

        return success_response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
            "is_new_user": created,
        })
