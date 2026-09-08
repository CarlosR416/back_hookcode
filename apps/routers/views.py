"""
Views for the routers application.

RouterViewSet   — CRUD for Router records (scoped to user's own routers).
UserRouterViewSet — manage user-router associations (owners only, or admin).
"""

import secrets
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.scripts.models import ScriptDownloadToken
from apps.scripts.serializers import (
    GenerateBootstrapTokenSerializer,
    ScriptDownloadTokenResponseSerializer,
)
from core.mixins import ActionPermissionsMixin, StandardResponseMixin
from core.responses import created_response, no_content_response, success_response

from services.mikrotik.client import MikroTikClient
from services.mikrotik.router import RouterService

from .models import Router, UserRouter
from .permissions import IsAdminOrReadOwner, IsRouterMember, IsRouterOwner
from .serializers import (
    RouterCreateSerializer,
    RouterSerializer,
    RouterWriteSerializer,
    UserRouterSerializer,
    UserRouterWriteSerializer,
)
from .services import (
    provision_router_defaults,
    sync_router_radius_user,
)


class RouterViewSet(ActionPermissionsMixin, StandardResponseMixin, ModelViewSet):
    """
    CRUD endpoints for registered MikroTik routers.

    list:                     GET  /api/routers/
    create:                   POST /api/routers/
    retrieve:                 GET  /api/routers/{id}/
    update:                   PUT  /api/routers/{id}/
    partial_update:           PATCH /api/routers/{id}/
    destroy:                  DELETE /api/routers/{id}/
    ping:                     GET  /api/routers/{id}/ping/
    resource:                 GET  /api/routers/{id}/resource/
    interfaces:               GET  /api/routers/{id}/interfaces/
    generate_bootstrap_token: POST /api/routers/{id}/generate-bootstrap-token/

    Access policy
    -------------
    - list / create           → authenticated (list is queryset-filtered per user)
    - retrieve / ping /
      resource / interfaces   → IsRouterMember (owner OR viewer)
    - update / partial_update
      / destroy /
      generate_bootstrap_token → IsRouterOwner (owner only)
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
        "generate_bootstrap_token": [IsRouterOwner],
    }

    def get_queryset(self):
        """
        Staff users see all active routers (or all if include_inactive=true).
        Regular users see only active routers they have any role on.
        """
        user = self.request.user
        base_qs = Router.objects.all()
        if not getattr(user, "is_staff", False) or not self.request.query_params.get(
            "include_inactive"
        ):
            base_qs = base_qs.filter(is_active=True)

        if getattr(user, "is_staff", False):
            return base_qs
        owned_router_ids = UserRouter.objects.filter(user=user).values_list(
            "router_id", flat=True
        )
        return base_qs.filter(pk__in=owned_router_ids)

    def get_serializer_class(self):
        if self.action == "create":
            return RouterCreateSerializer
        if self.action in ["update", "partial_update"]:
            return RouterWriteSerializer
        return RouterSerializer

    @transaction.atomic
    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        """Create the router with dynamic credentials/port, assign creator as OWNER, and register RADIUS user."""
        defaults = provision_router_defaults()
        router = serializer.save(**defaults)
        UserRouter.objects.create(
            user=self.request.user,
            router=router,
            role=UserRouter.RouterRole.OWNER,
        )
        sync_router_radius_user(router)

    def perform_destroy(self, instance: Router) -> None:
        """Perform logical deletion on router (is_active=False) and revoke RADIUS credentials."""
        instance.soft_delete()

    def _get_service(self, router: Router) -> RouterService:
        """Build a RouterService for the given router instance."""
        client = MikroTikClient(
            host=router.host,
            username=router.api_username,
            password=router.api_password,
            port=router.api_port or router.port,
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

    @extend_schema(
        request=GenerateBootstrapTokenSerializer,
        responses={201: ScriptDownloadTokenResponseSerializer},
        tags=["routers"],
    )
    @action(detail=True, methods=["post"], url_path="generate-bootstrap-token")
    def generate_bootstrap_token(self, request: Request, pk: int | None = None) -> Response:
        """
        Generate a single-use (Burn-on-Read) download token for this router.
        Can be used by RouterOS fetch command to safely download sensitive setup configurations.
        """
        router = self.get_object()
        serializer = GenerateBootstrapTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        template = data.get("template")
        variables = data.get("variables", {})
        expiration_minutes = data.get(
            "expiration_minutes",
            getattr(settings, "SCRIPT_TOKEN_EXPIRATION_MINUTES", 10),
        )
        include_cleanup = data.get("include_cleanup", True)
        filename = data.get("filename", "setup.rsc")

        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(minutes=expiration_minutes)

        token_record = ScriptDownloadToken.objects.create(
            router=router,
            template=template,
            variables_used=variables,
            token=token,
            expires_at=expires_at,
            include_cleanup=include_cleanup,
            filename=filename,
        )

        download_url = request.build_absolute_uri(
            reverse("scripts:script-download", kwargs={"token": token})
        )
        routeros_cmd = (
            f'/tool fetch url="{download_url}" mode=https dst-path="{filename}"; '
            f':delay 1s; /import {filename}'
        )

        return created_response(
            {
                "token": token_record.token,
                "download_url": download_url,
                "routeros_command": routeros_cmd,
                "expires_at": token_record.expires_at,
            }
        )


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
        Regular users see only memberships for active routers.
        """
        user = self.request.user
        if getattr(user, "is_staff", False):
            return UserRouter.objects.select_related("user", "router").all()
        return UserRouter.objects.select_related("user", "router").filter(
            user=user, router__is_active=True
        )

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
        return created_response(UserRouterSerializer(instance).data)

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
        return no_content_response()
