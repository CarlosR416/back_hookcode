"""
Views for the routers application.
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.responses import success_response
from services.mikrotik.client import MikroTikClient
from services.mikrotik.router import RouterService

from .models import Router
from .serializers import RouterSerializer, RouterWriteSerializer


class RouterViewSet(ModelViewSet):
    """
    CRUD endpoints for registered MikroTik routers.

    list:       GET  /api/routers/
    create:     POST /api/routers/
    retrieve:   GET  /api/routers/{id}/
    update:     PUT  /api/routers/{id}/
    partial_update: PATCH /api/routers/{id}/
    destroy:    DELETE /api/routers/{id}/
    ping:       GET  /api/routers/{id}/ping/
    resource:   GET  /api/routers/{id}/resource/
    interfaces: GET  /api/routers/{id}/interfaces/
    """

    queryset = Router.objects.all()
    permission_classes = [IsAuthenticated]

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
