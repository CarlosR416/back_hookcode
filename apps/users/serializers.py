"""
Serializers for the users application.
"""

from django.contrib.auth import get_user_model
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

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "username", "first_name", "last_name", "password", "password_confirm"]

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data: dict) -> User:
        return User.objects.create_user(**validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for in-place password change."""

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs: dict) -> dict:
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "New passwords do not match."}
            )
        return attrs
