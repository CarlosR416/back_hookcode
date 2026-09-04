"""
Global DRF exception handler — wraps all errors in a consistent JSON envelope.
"""

from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler

from services.mikrotik.exceptions import MikroTikAPIError, MikroTikConnectionError


def custom_exception_handler(exc: Exception, context: Any) -> Response | None:
    """
    Extend DRF's default handler to:
      - Wrap all errors under {"error": {...}} for consistency.
      - Convert MikroTik service exceptions to HTTP 502.
    """
    # Let DRF handle standard exceptions first
    response = exception_handler(exc, context)

    if isinstance(exc, MikroTikConnectionError):
        return Response(
            {"error": {"code": "mikrotik_unreachable", "detail": str(exc)}},
            status=502,
        )

    if isinstance(exc, MikroTikAPIError):
        return Response(
            {"error": {"code": "mikrotik_api_error", "detail": str(exc)}},
            status=502,
        )

    if response is not None:
        response.data = {"error": response.data}

    return response
