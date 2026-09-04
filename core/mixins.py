"""
Reusable ViewSet mixins shared across all apps.
"""

from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response


class ActionPermissionsMixin:
    """
    Override get_permissions() per action using an action_permissions dict.

    Usage in a ViewSet:
        action_permissions = {
            "list": [IsAuthenticated],
            "destroy": [IsAdminUser],
        }
    """

    action_permissions: dict = {}

    def get_permissions(self) -> list:
        permission_classes = self.action_permissions.get(
            self.action, self.permission_classes  # type: ignore[attr-defined]
        )
        return [permission() for permission in permission_classes]
