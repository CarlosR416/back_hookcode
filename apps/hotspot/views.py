"""
Views for the hotspot application.
"""

from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.responses import created_response, success_response
from services.mikrotik.client import MikroTikClient
from services.mikrotik.hotspot import HotspotService

from .models import HotspotProfile, HotspotUser
from .serializers import (
    HotspotProfileSerializer,
    HotspotUserSerializer,
    HotspotUserWriteSerializer,
)


def _get_hotspot_service(router) -> HotspotService:
    """Instantiate a HotspotService from a Router model instance."""
    client = MikroTikClient(
        host=router.host,
        username=router.api_username,
        password=router.api_password,
        port=router.port,
        ssl_verify=router.ssl_verify,
    )
    return HotspotService(client)


class HotspotProfileViewSet(ModelViewSet):
    """
    CRUD endpoints for hotspot profiles.

    list:       GET  /api/hotspot/profiles/
    create:     POST /api/hotspot/profiles/
    retrieve:   GET  /api/hotspot/profiles/{id}/
    update:     PUT  /api/hotspot/profiles/{id}/
    destroy:    DELETE /api/hotspot/profiles/{id}/
    sync:       POST /api/hotspot/profiles/{id}/sync/
    """

    queryset = HotspotProfile.objects.select_related("router").all()
    serializer_class = HotspotProfileSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["router"]

    @action(detail=True, methods=["post"], url_path="sync")
    def sync(self, request: Request, pk: int | None = None) -> Response:
        """
        Push local profile settings to the MikroTik router.
        Creates the profile if it does not exist, otherwise updates it.
        """
        profile = self.get_object()
        svc = _get_hotspot_service(profile.router)
        payload = {"name": profile.name}
        if profile.rate_limit:
            payload["rate-limit"] = profile.rate_limit
        if profile.session_timeout:
            payload["session-timeout"] = profile.session_timeout

        if profile.mk_id:
            result = svc.client.patch(f"{svc.PROFILES_PATH}/{profile.mk_id}", json=payload)
        else:
            result = svc.create_profile(
                name=profile.name,
                rate_limit=profile.rate_limit,
            )
            profile.mk_id = result.get(".id", "")
            profile.save(update_fields=["mk_id"])

        return success_response(result)


class HotspotUserViewSet(ModelViewSet):
    """
    CRUD endpoints for hotspot users.

    list:       GET  /api/hotspot/users/
    create:     POST /api/hotspot/users/
    retrieve:   GET  /api/hotspot/users/{id}/
    update:     PUT  /api/hotspot/users/{id}/
    destroy:    DELETE /api/hotspot/users/{id}/
    enable:     POST /api/hotspot/users/{id}/enable/
    disable:    POST /api/hotspot/users/{id}/disable/
    sessions:   GET  /api/hotspot/sessions/
    """

    queryset = HotspotUser.objects.select_related("router", "profile").all()
    permission_classes = [IsAuthenticated]
    filterset_fields = ["router", "profile", "is_disabled"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return HotspotUserWriteSerializer
        return HotspotUserSerializer

    def perform_create(self, serializer) -> None:
        """Create the user on the router first, then persist locally."""
        router = serializer.validated_data["router"]
        profile = serializer.validated_data.get("profile")
        svc = _get_hotspot_service(router)

        result = svc.create_user(
            name=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
            profile=profile.name if profile else "default",
            comment=serializer.validated_data.get("comment", ""),
        )
        serializer.save(mk_id=result.get(".id", ""))

    @action(detail=True, methods=["post"], url_path="enable")
    def enable(self, request: Request, pk: int | None = None) -> Response:
        """Enable a hotspot user on the router."""
        hotspot_user = self.get_object()
        svc = _get_hotspot_service(hotspot_user.router)
        result = svc.enable_user(hotspot_user.mk_id)
        hotspot_user.is_disabled = False
        hotspot_user.save(update_fields=["is_disabled"])
        return success_response(result)

    @action(detail=True, methods=["post"], url_path="disable")
    def disable(self, request: Request, pk: int | None = None) -> Response:
        """Disable a hotspot user on the router."""
        hotspot_user = self.get_object()
        svc = _get_hotspot_service(hotspot_user.router)
        result = svc.disable_user(hotspot_user.mk_id)
        hotspot_user.is_disabled = True
        hotspot_user.save(update_fields=["is_disabled"])
        return success_response(result)

    @action(detail=False, methods=["get"], url_path="sessions")
    def sessions(self, request: Request) -> Response:
        """
        Return active hotspot sessions.
        Requires ?router=<id> query param to specify which router to query.
        """
        from apps.routers.models import Router

        router_id = request.query_params.get("router")
        if not router_id:
            return Response(
                {"error": {"code": "missing_param", "detail": "'router' query param is required."}},
                status=400,
            )
        router = Router.objects.get(pk=router_id)
        svc = _get_hotspot_service(router)
        return success_response(svc.list_active_sessions())
