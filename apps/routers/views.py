"""
Views for the routers application.

RouterViewSet   — CRUD for Router records (scoped to user's own routers).
UserRouterViewSet — manage user-router associations (owners only, or admin).
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from core.mixins import ActionPermissionsMixin
from core.responses import success_response

from services.mikrotik.client import MikroTikClient
from services.mikrotik.router import RouterService

from .models import Router, UserRouter
from .permissions import IsAdminOrReadOwner, IsRouterMember, IsRouterOwner
from .serializers import (
    RouterSerializer,
    RouterWriteSerializer,
    UserRouterSerializer,
    UserRouterWriteSerializer,
)


class RouterViewSet(ActionPermissionsMixin, ModelViewSet):
    """
    CRUD endpoints for registered MikroTik routers.

    list:           GET  /api/routers/
    create:         POST /api/routers/
    retrieve:       GET  /api/routers/{id}/
    update:         PUT  /api/routers/{id}/
    partial_update: PATCH /api/routers/{id}/
    destroy:        DELETE /api/routers/{id}/
    ping:           GET  /api/routers/{id}/ping/
    resource:       GET  /api/routers/{id}/resource/
    interfaces:     GET  /api/routers/{id}/interfaces/

    Access policy
    -------------
    - list / create           → authenticated (list is queryset-filtered per user)
    - retrieve / ping /
      resource / interfaces   → IsRouterMember (owner OR viewer)
    - update / partial_update
      / destroy               → IsRouterOwner (owner only)
    """

    permission_classes = [IsAuthenticated]

    # Per-action permission overrides (ActionPermissionsMixin)
    action_permissions = {
        "retrieve": [IsRouterMember],
        "ping": [IsRouterMember],
        "resource": [IsRouterMember],
        "interfaces": [IsRouterMember],
        "update": [IsRouterOwner],
        "partial_update": [IsRouterOwner],
        "destroy": [IsRouterOwner],
    }

    def get_queryset(self):
        """
        Staff users see all routers.
        Regular users see only the routers they have any role on.
        """
        user = self.request.user
        if user.is_staff:
            return Router.objects.all()
        owned_router_ids = UserRouter.objects.filter(user=user).values_list(
            "router_id", flat=True
        )
        return Router.objects.filter(pk__in=owned_router_ids)

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return RouterWriteSerializer
        return RouterSerializer

    def _get_service(self, router: Router) -> RouterService:
        """Build a RouterService for the given router instance."""
        client = MikroTikClient(
            host=router.host,
            username=router.api_username,
            password=router.api_password,
            port=router.port,
            ssl_verify=router.ssl_verify,
        )
        return RouterService(client)

    # ── Live router actions ────────────────────────────────────────────────────

    @action(detail=True, methods=["get"], url_path="ping")
    def ping(self, request: Request, pk: int | None = None) -> Response:
        """
        Test live connectivity to the router.
        Returns the router identity if reachable.
        """
        router = self.get_object()
        svc = self._get_service(router)
        identity = svc.get_identity()
        return success_response({"identity": identity, "router_id": router.id})

    @action(detail=True, methods=["get"], url_path="resource")
    def resource(self, request: Request, pk: int | None = None) -> Response:
        """Return live system resource information (CPU, memory, uptime)."""
        router = self.get_object()
        svc = self._get_service(router)
        return success_response(svc.get_resource())

    @action(detail=True, methods=["get"], url_path="interfaces")
    def interfaces(self, request: Request, pk: int | None = None) -> Response:
        """Return all network interfaces on the router."""
        router = self.get_object()
        svc = self._get_service(router)
        return success_response(svc.list_interfaces())


class UserRouterViewSet(ActionPermissionsMixin, GenericViewSet):
    """
    Manage user-router associations.

    list:           GET  /api/routers/memberships/
    create:         POST /api/routers/memberships/
    retrieve:       GET  /api/routers/memberships/{id}/
    update:         PUT  /api/routers/memberships/{id}/
    partial_update: PATCH /api/routers/memberships/{id}/
    destroy:        DELETE /api/routers/memberships/{id}/

    Access policy
    -------------
    - Any authenticated user can list/retrieve their own memberships.
    - Only staff (admins) can create/update/delete memberships.
      (Owners self-managing their router memberships is a phase-2 feature.)
    """

    permission_classes = [IsAuthenticated]

    action_permissions = {
        "create": [IsAdminUser],
        "update": [IsAdminUser],
        "partial_update": [IsAdminUser],
        "destroy": [IsAdminUser],
    }

    def get_queryset(self):
        """
        Staff sees all memberships.
        Regular users see only their own memberships.
        """
        user = self.request.user
        if user.is_staff:
            return UserRouter.objects.select_related("user", "router").all()
        return UserRouter.objects.select_related("user", "router").filter(user=user)

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return UserRouterWriteSerializer
        return UserRouterSerializer

    def list(self, request: Request) -> Response:
        """List all router memberships visible to the requesting user."""
        qs = self.get_queryset()
        serializer = self.get_serializer(qs, many=True)
        return success_response(serializer.data)

    def retrieve(self, request: Request, pk: int | None = None) -> Response:
        """Retrieve a single router membership."""
        instance = self.get_object()
        return success_response(self.get_serializer(instance).data)

    def create(self, request: Request) -> Response:
        """Create a user-router membership (admin only)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            UserRouterSerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, pk: int | None = None, **kwargs) -> Response:
        """Update (replace) a membership's role (admin only)."""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(UserRouterSerializer(serializer.instance).data)

    def partial_update(self, request: Request, pk: int | None = None) -> Response:
        return self.update(request, pk, partial=True)

    def destroy(self, request: Request, pk: int | None = None) -> Response:
        """Remove a user-router membership (admin only)."""
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
