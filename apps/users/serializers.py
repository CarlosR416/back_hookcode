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

    class Meta:
        model = User
        fields = ["id", "email", "username", "first_name", "last_name", "is_active", "date_joined"]
        read_only_fields = ["id", "date_joined"]


class RegisterSerializer(serializers.ModelSerializer):
    """Write serializer for new user registration."""

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

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": _("Passwords do not match.")})
        return attrs

    @transaction.atomic
    def create(self, validated_data: dict) -> User:
        from .emails import generate_and_send_otp

        validated_data["username"] = validated_data["email"][:150]
        validated_data["is_active"] = False
        user = User.objects.create_user(**validated_data)
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
