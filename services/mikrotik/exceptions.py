"""
Custom exceptions for the MikroTik service layer.

These are caught by the global exception handler in core/exceptions.py
and converted to HTTP 502 responses.
"""


class MikroTikConnectionError(Exception):
    """Raised when the client cannot reach the MikroTik router (network/timeout)."""


class MikroTikAuthError(MikroTikConnectionError):
    """Raised when MikroTik returns HTTP 401/403 (bad credentials)."""


class MikroTikAPIError(Exception):
    """Raised when MikroTik returns an unexpected error response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
