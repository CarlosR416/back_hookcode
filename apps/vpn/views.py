"""
Views for the VPN application.

Provides management endpoints for VPN server nodes and serving public certificates.
"""

from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.mixins import ActionPermissionsMixin, StandardResponseMixin
from core.responses import success_response

from .models import VpnNode
from .serializers import (
    VpnNodeCertificateSerializer,
    VpnNodeSerializer,
    VpnNodeWriteSerializer,
)
from .services import VpnNodeService


class VpnNodeViewSet(ActionPermissionsMixin, StandardResponseMixin, ModelViewSet):
    """
    CRUD endpoints for VPN server nodes.

    list:        GET    /api/vpn/nodes/
    create:      POST   /api/vpn/nodes/
    retrieve:    GET    /api/vpn/nodes/{id}/
    update:      PUT    /api/vpn/nodes/{id}/
    destroy:     DELETE /api/vpn/nodes/{id}/
    certificate: GET    /api/vpn/nodes/{id}/certificate/
    """

    permission_classes = [IsAuthenticated]
    queryset = VpnNode.objects.all()

    action_permissions = {
        "create": [IsAdminUser],
        "update": [IsAdminUser],
        "partial_update": [IsAdminUser],
        "destroy": [IsAdminUser],
        "list": [IsAuthenticated],
        "retrieve": [IsAuthenticated],
        "certificate": [AllowAny],
    }

    def get_queryset(self):
        """
        Staff sees all nodes.
        Regular users only see active nodes.
        """
        user = self.request.user
        if getattr(user, "is_staff", False):
            return VpnNode.objects.all()
        return VpnNode.objects.filter(is_active=True)

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return VpnNodeWriteSerializer
        return VpnNodeSerializer

    @extend_schema(
        responses={200: VpnNodeCertificateSerializer},
        tags=["vpn"],
        summary="Serve the public certificate for a VPN node",
    )
    @action(detail=True, methods=["get"], url_path="certificate")
    def certificate(self, request: Request, pk: int | None = None) -> Response | HttpResponse:
        """
        Serve the public certificate or public key of the specified VPN node.
        Supports JSON envelope or raw text with `?format=raw` query parameter.
        """
        node = self.get_object()
        cert_content = VpnNodeService.get_public_certificate(node)

        # Support raw download/text stream for automated scripts (RouterOS fetch, curl)
        if (
            request.query_params.get("raw") == "true"
            or request.query_params.get("download") == "true"
        ):
            filename = (
                f"{node.name}.crt"
                if node.vpn_type != VpnNode.VpnType.WIREGUARD
                else f"{node.name}.pub"
            )
            response = HttpResponse(cert_content, content_type="text/plain; charset=utf-8")
            response["Content-Disposition"] = f'inline; filename="{filename}"'
            return response

        return success_response(
            {
                "node_id": node.pk,
                "name": node.name,
                "vpn_type": node.vpn_type,
                "public_certificate": cert_content,
            }
        )
