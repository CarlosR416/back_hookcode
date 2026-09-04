"""
Views for the hotspot application.
"""

from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from django.http import HttpResponse
from django.utils.translation import gettext as _

from core.responses import created_response, success_response
from services.mikrotik.client import MikroTikClient
from services.mikrotik.hotspot import HotspotService
from services.hotspot_template import HotspotTemplateRendererFactory

from .models import HotspotProfile, HotspotTemplate, HotspotTemplateFile, HotspotUser
from .serializers import (
    HotspotProfileSerializer,
    HotspotTemplateFileDetailSerializer,
    HotspotTemplateFileSerializer,
    HotspotTemplateFileWriteSerializer,
    HotspotTemplateSerializer,
    HotspotTemplateWriteSerializer,
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
                {"error": {"code": "missing_param", "detail": _("'router' query param is required.")}},
                status=400,
            )
        router = Router.objects.get(pk=router_id)
        svc = _get_hotspot_service(router)
        return success_response(svc.list_active_sessions())


# ---------------------------------------------------------------------------
# Hotspot template views
# ---------------------------------------------------------------------------


class HotspotTemplateViewSet(ModelViewSet):
    """
    CRUD + rendering endpoints for portal templates.

    list:         GET  /api/hotspot/templates/
    create:       POST /api/hotspot/templates/
    retrieve:     GET  /api/hotspot/templates/{id}/
    update:       PUT  /api/hotspot/templates/{id}/
    partial_update: PATCH /api/hotspot/templates/{id}/
    destroy:      DELETE /api/hotspot/templates/{id}/

    preview-zip:  GET  /api/hotspot/templates/{id}/preview-zip/
        Download a ZIP of ALL files rendered in PREVIEW mode.
        Useful for checking the full portal before deployment.

    download-zip: GET  /api/hotspot/templates/{id}/download-zip/
        Download a ZIP of ALL files rendered in DOWNLOAD (device-ready) mode.
        Upload the extracted contents to the router's /flash/hotspot/ directory.
    """

    queryset = HotspotTemplate.objects.prefetch_related("files").all()
    permission_classes = [IsAuthenticated]
    filterset_fields = ["vendor", "is_active"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return HotspotTemplateWriteSerializer
        return HotspotTemplateSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def _get_renderer(self, template: HotspotTemplate):
        return HotspotTemplateRendererFactory.for_vendor(template.vendor)

    def _zip_response(
        self, template: HotspotTemplate, mode: str, overrides: dict | None
    ) -> HttpResponse:
        """Build and return a ZIP HttpResponse for the given mode."""
        renderer = self._get_renderer(template)
        if mode == "preview":
            # For preview ZIP we render each file in preview mode manually
            import io, zipfile

            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                for f in template.files.order_by("order", "filename"):
                    zf.writestr(f.filename, renderer.render_preview(template, f, overrides))
            buffer.seek(0)
            data = buffer.read()
        else:
            data = renderer.build_zip(template, overrides)

        zip_name = f"{template.name.replace(' ', '_')}_{mode}.zip"
        response = HttpResponse(data, content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{zip_name}"'
        return response

    @action(detail=True, methods=["get"], url_path="preview-zip")
    def preview_zip(self, request: Request, pk: int | None = None) -> HttpResponse:
        """
        Download a ZIP of all files rendered for in-browser preview.
        Optional query param: pass any key=value to override template variables.
        """
        template = self.get_object()
        overrides = request.query_params.dict() or None
        return self._zip_response(template, mode="preview", overrides=overrides)

    @action(detail=True, methods=["get"], url_path="download-zip")
    def download_zip(self, request: Request, pk: int | None = None) -> HttpResponse:
        """
        Download a device-ready ZIP of all template files.
        Extract its contents and upload to /flash/hotspot/ on the MikroTik router.
        Optional query param overrides for Jinja2 variables.
        """
        template = self.get_object()
        overrides = request.query_params.dict() or None
        return self._zip_response(template, mode="download", overrides=overrides)


class HotspotTemplateFileViewSet(ModelViewSet):
    """
    CRUD + per-file rendering for individual template files.

    list:         GET  /api/hotspot/template-files/
    create:       POST /api/hotspot/template-files/
    retrieve:     GET  /api/hotspot/template-files/{id}/
    update:       PUT  /api/hotspot/template-files/{id}/
    partial_update: PATCH /api/hotspot/template-files/{id}/
    destroy:      DELETE /api/hotspot/template-files/{id}/

    preview:      GET  /api/hotspot/template-files/{id}/preview/
        Returns the rendered HTML of this single file in preview mode.
        Sets Content-Type from file.mime_type.

    download:     GET  /api/hotspot/template-files/{id}/download/
        Returns the device-ready content of this single file.
        Sets Content-Disposition so the browser saves it with the correct filename.
    """

    permission_classes = []
    filterset_fields = ["template", "role"]

    def get_queryset(self):
        return HotspotTemplateFile.objects.select_related("template").all()

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return HotspotTemplateFileWriteSerializer
        if self.action == "retrieve":
            return HotspotTemplateFileDetailSerializer
        return HotspotTemplateFileSerializer

    def _render_file(
        self, file: HotspotTemplateFile, mode: str, overrides: dict | None
    ) -> str:
        renderer = HotspotTemplateRendererFactory.for_vendor(file.template.vendor)
        if mode == "preview":
            return renderer.render_preview(file.template, file, overrides)
        return renderer.render_download(file.template, file, overrides)

    @action(detail=True, methods=["get"], url_path="preview")
    def preview(self, request: Request, pk: int | None = None) -> HttpResponse:
        """
        Render this file in preview mode and stream it as the original MIME type.
        Useful to embed the result in an <iframe> for a live preview in the UI.
        """
        file = self.get_object()
        overrides = request.query_params.dict() or None
        content = self._render_file(file, mode="preview", overrides=overrides)
        return HttpResponse(content, content_type=file.mime_type)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request: Request, pk: int | None = None) -> HttpResponse:
        """
        Render this file in device-ready mode and return it as a file download.
        """
        file = self.get_object()
        overrides = request.query_params.dict() or None
        content = self._render_file(file, mode="download", overrides=overrides)
        response = HttpResponse(content, content_type=file.mime_type)
        response["Content-Disposition"] = f'attachment; filename="{file.filename}"'
        return response

