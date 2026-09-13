"""
Serializers for the users application.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Read serializer — safe fields only, no password returned."""

    max_routers = serializers.IntegerField(
        read_only=True,
        help_text=_("Maximum number of active routers allowed for this account (null if unlimited)."),
    )
    owned_routers_count = serializers.IntegerField(
        read_only=True,
        help_text=_("Current count of active routers owned by this account."),
    )
    can_add_router = serializers.BooleanField(
        read_only=True,
        help_text=_("Whether the user is eligible to add another router under their current plan."),
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "plan",
            "max_routers",
            "owned_routers_count",
            "can_add_router",
            "is_active",
            "is_email_verified",
            "date_joined",
        ]
        read_only_fields = [
            "id",
            "plan",
            "max_routers",
            "owned_routers_count",
            "can_add_router",
            "date_joined",
            "is_email_verified",
        ]


class RegisterSerializer(serializers.ModelSerializer):
    """Write serializer for new user registration."""

    email = serializers.EmailField(
        required=True,
        help_text=_("Email address of the user."),
    )
    first_name = serializers.CharField(
        required=True,
        max_length=150,
        help_text=_("First name of the user."),
    )
    last_name = serializers.CharField(
        required=True,
        max_length=150,
        help_text=_("Last name of the user."),
    )
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "password", "password_confirm"]

    def validate_email(self, value: str) -> str:
        value = value.lower().strip()
        existing_user = User.objects.filter(email__iexact=value).first()
        if existing_user and existing_user.is_email_verified:
            raise serializers.ValidationError(_("A user with that email address already exists."))
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": _("Passwords do not match.")})
        return attrs

    @transaction.atomic
    def create(self, validated_data: dict) -> User:
        from .emails import generate_and_send_otp

        email = validated_data["email"].lower().strip()
        first_name = validated_data["first_name"]
        last_name = validated_data["last_name"]
        password = validated_data["password"]

        existing_user = User.objects.filter(email__iexact=email).first()

        if existing_user:
            if existing_user.is_email_verified:
                raise serializers.ValidationError(
                    {"email": _("A user with that email address already exists.")}
                )
            # Replace unconfirmed user's data with fresh registration details
            existing_user.first_name = first_name
            existing_user.last_name = last_name
            existing_user.username = email[:150]
            existing_user.set_password(password)
            existing_user.is_active = False
            existing_user.is_email_verified = False
            existing_user.save()
            user = existing_user
        else:
            user = User.objects.create_user(
                email=email,
                username=email[:150],
                first_name=first_name,
                last_name=last_name,
                password=password,
                is_active=False,
                is_email_verified=False,
            )

        try:
            generate_and_send_otp(user)
        except Exception as exc:
            raise serializers.ValidationError(
                {"email": _("Failed to send verification email. Please try again later.")}
            ) from exc
        return user


class VerifyOTPSerializer(serializers.Serializer):
    """Serializer for 6-digit OTP email verification."""

    email = serializers.EmailField(
        required=True,
        help_text=_("The email address of the account to verify."),
    )
    otp = serializers.CharField(
        required=True,
        min_length=6,
        max_length=6,
        help_text=_("The 6-digit numeric OTP code received via email."),
    )

    def validate_otp(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError(_("The OTP code must contain only digits."))
        return value


class ResendOTPSerializer(serializers.Serializer):
    """Serializer for requesting a fresh OTP verification code."""

    email = serializers.EmailField(
        required=True,
        help_text=_("The email address of the account to resend the code to."),
    )


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for in-place password change."""

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs: dict) -> dict:
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": _("New passwords do not match.")}
            )
        return attrs


class GoogleLoginSerializer(serializers.Serializer):
    """Serializer for Google Firebase login token validation."""

    firebase_token = serializers.CharField(
        required=True,
        help_text=_("The Firebase ID token obtained from Google Sign-In."),
    )

    def validate_firebase_token(self, value):
        from .firebase import verify_google_token
        return verify_google_token(value)


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for requesting a password reset OTP."""

    email = serializers.EmailField(
        required=True,
        help_text=_("The email address of the account requesting password reset."),
    )

    def validate_email(self, value: str) -> str:
        return value.lower().strip()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for verifying OTP and setting a new password."""

    email = serializers.EmailField(
        required=True,
        help_text=_("The email address of the account."),
    )
    otp = serializers.CharField(
        required=True,
        min_length=6,
        max_length=6,
        help_text=_("The 6-digit numeric OTP code received via email."),
    )
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        help_text=_("The new password (minimum 8 characters)."),
    )
    password_confirm = serializers.CharField(
        write_only=True,
        help_text=_("Confirmation of the new password."),
    )

    def validate_email(self, value: str) -> str:
        return value.lower().strip()

    def validate_otp(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError(_("The OTP code must contain only digits."))
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": _("Passwords do not match.")}
            )
        from django.contrib.auth.password_validation import validate_password
        validate_password(attrs["password"])
        return attrs

