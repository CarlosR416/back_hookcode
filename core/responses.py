"""
Standard API response helpers for consistent response shapes.
"""

from rest_framework.response import Response


def success_response(data: dict | list, status: int = 200, **kwargs) -> Response:
    """Return a standard success envelope."""
    return Response({"data": data, **kwargs}, status=status)


def created_response(data: dict | list, **kwargs) -> Response:
    """Return a 201 Created response."""
    return success_response(data, status=201, **kwargs)


def no_content_response() -> Response:
    """Return a 204 No Content response."""
    return Response(status=204)


def error_response(detail: str, code: str = "error", status: int = 400) -> Response:
    """Return a standard error envelope."""
    return Response({"error": {"code": code, "detail": detail}}, status=status)
