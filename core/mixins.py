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


class StandardResponseMixin:
    """
    Mixin for ModelViewSets ensuring standard response envelopes:
      - create -> {"data": ...} (status 201)
      - retrieve -> {"data": ...} (status 200)
      - update / partial_update -> {"data": ...} (status 200)
      - destroy -> empty response (status 204)
    """

    def create(self, request: Request, *args, **kwargs) -> Response:
        from core.responses import created_response

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return created_response(serializer.data, headers=headers)

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        from core.responses import success_response

        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_response(serializer.data)

    def update(self, request: Request, *args, **kwargs) -> Response:
        from core.responses import success_response

        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return success_response(serializer.data)

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        from core.responses import no_content_response

        instance = self.get_object()
        self.perform_destroy(instance)
        return no_content_response()
