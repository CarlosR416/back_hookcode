"""
Global DRF exception handler — wraps all errors in a consistent JSON envelope.
"""

from typing import Any

import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from services.mikrotik.exceptions import MikroTikAPIError, MikroTikConnectionError

logger = logging.getLogger(__name__)


def custom_exception_handler(exc: Exception, context: Any) -> Response:
    """
    Extend DRF's default handler to:
      - Wrap all errors under {"error": {...}} for consistency.
      - Convert MikroTik service exceptions to HTTP 502.
      - Return standardized JSON response for unhandled 500 exceptions.
    """
    if isinstance(exc, MikroTikConnectionError):
        return Response(
            {"error": {"code": "mikrotik_unreachable", "detail": str(exc)}},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    if isinstance(exc, MikroTikAPIError):
        return Response(
            {"error": {"code": "mikrotik_api_error", "detail": str(exc)}},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    # Let DRF handle standard exceptions first
    response = exception_handler(exc, context)

    if response is not None:
        response.data = {"error": response.data}
        return response

    # Fallback for unhandled server exceptions (500)
    logger.exception("Unhandled server exception: %s", exc)
    detail = str(exc) if getattr(settings, "DEBUG", False) else "An unexpected error occurred."
    return Response(
        {"error": {"code": "internal_server_error", "detail": detail}},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )

