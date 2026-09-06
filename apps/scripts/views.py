import secrets
from datetime import timedelta

from django.conf import settings
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from drf_spectacular.utils import OpenApiResponse, extend_schema

from apps.routers.models import UserRouter
from apps.routers.permissions import IsRouterOwner
from core.mixins import StandardResponseMixin
from core.responses import created_response, error_response, success_response

from .models import RouterScriptExecution, ScriptDownloadToken, ScriptTemplate
from .serializers import (
    GenerateBootstrapTokenSerializer,
    RouterScriptExecutionSerializer,
    ScriptDownloadTokenResponseSerializer,
    ScriptTemplateSerializer,
)


class ScriptTemplateViewSet(StandardResponseMixin, ReadOnlyModelViewSet):
    queryset = ScriptTemplate.objects.all()
    serializer_class = ScriptTemplateSerializer
    permission_classes = [IsAuthenticated]


class RouterScriptExecutionViewSet(StandardResponseMixin, ModelViewSet):
    queryset = RouterScriptExecution.objects.all()
    serializer_class = RouterScriptExecutionSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer: RouterScriptExecutionSerializer) -> None:
        serializer.save(status="PENDING")

    @extend_schema(
        request=GenerateBootstrapTokenSerializer,
        responses={201: ScriptDownloadTokenResponseSerializer},
        tags=["scripts"],
    )
    @action(detail=True, methods=["post"], url_path="generate-token")
    def generate_token(self, request: Request, pk: int | None = None) -> Response:
        """Generate a single-use (Burn-on-Read) download token for this script execution."""
        execution = self.get_object()

        # Enforce router owner permission
        if not (request.user.is_staff or execution.router.user_routers.filter(user=request.user, role=UserRouter.RouterRole.OWNER).exists()):
            return error_response(
                detail=_("You must be the owner of this router to generate download tokens."),
                code="permission_denied",
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = GenerateBootstrapTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        expiration_minutes = data.get(
            "expiration_minutes",
            getattr(settings, "SCRIPT_TOKEN_EXPIRATION_MINUTES", 10),
        )
        include_cleanup = data.get("include_cleanup", True)
        filename = data.get("filename", "setup.rsc")

        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(minutes=expiration_minutes)

        token_record = ScriptDownloadToken.objects.create(
            router=execution.router,
            execution=execution,
            template=execution.template,
            variables_used=execution.variables_used,
            token=token,
            expires_at=expires_at,
            include_cleanup=include_cleanup,
            filename=filename,
        )

        download_url = request.build_absolute_uri(
            reverse("scripts:script-download", kwargs={"token": token})
        )
        routeros_cmd = f'/tool fetch url="{download_url}" mode=https dst-path="{filename}"; :delay 1s; /import {filename}'

        return created_response(
            {
                "token": token_record.token,
                "download_url": download_url,
                "routeros_command": routeros_cmd,
                "expires_at": token_record.expires_at,
            }
        )


@extend_schema(
    summary="Download rendered RouterOS script via single-use token",
    description="Serves the compiled .rsc script and burns the token immediately (Burn-on-Read).",
    tags=["scripts"],
    responses={
        (200, "text/plain"): OpenApiResponse(description="Rendered RouterOS script file (.rsc)"),
        410: OpenApiResponse(description="Token is invalid, has expired, or has already been used."),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def download_script(request: Request, token: str) -> HttpResponse | Response:
    """
    Public single-use (Burn-on-Read) endpoint for downloading RouterOS scripts.
    Burned immediately upon first successful read. Subsequent attempts return HTTP 410.
    """
    try:
        token_record = ScriptDownloadToken.objects.get(token=token)
    except ScriptDownloadToken.DoesNotExist:
        return error_response(
            detail=_("The provisioning script link is invalid, has expired, or has already been used."),
            code="token_invalid_or_expired",
            status=status.HTTP_410_GONE,
        )

    if not token_record.is_valid():
        return error_response(
            detail=_("The provisioning script link is invalid, has expired, or has already been used."),
            code="token_invalid_or_expired",
            status=status.HTTP_410_GONE,
        )

    # Burn token immediately upon access
    token_record.burn()

    script_content = token_record.rendered_content

    response = HttpResponse(script_content, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{token_record.filename}"'
    return response
