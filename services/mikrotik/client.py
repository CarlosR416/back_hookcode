"""
Low-level HTTP client for the MikroTik RouterOS REST API.

All requests are authenticated via HTTP Basic Auth against
https://<host>:<port>/rest — available from RouterOS v7.1+.

Usage:
    client = MikroTikClient(host="192.168.88.1", username="admin", password="secret")
    result = client.get("ip/address")
    client.post("ip/hotspot/user", json={"name": "john", "password": "pass"})
"""

import logging
from typing import Any
from urllib.parse import urljoin

import requests
from django.conf import settings

from .exceptions import MikroTikAPIError, MikroTikAuthError, MikroTikConnectionError

logger = logging.getLogger(__name__)


class MikroTikClient:
    """
    Thin wrapper around the MikroTik RouterOS REST API.

    Args:
        host:        Router IP address or hostname.
        username:    RouterOS API username.
        password:    RouterOS API password.
        port:        HTTPS port (default from settings).
        ssl_verify:  Verify SSL certificate (default from settings).
        timeout:     Request timeout in seconds.
    """

    DEFAULT_TIMEOUT = 10

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int | None = None,
        ssl_verify: bool | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.host = host
        self.port = port if port is not None else settings.MIKROTIK_DEFAULT_PORT
        self.ssl_verify = ssl_verify if ssl_verify is not None else settings.MIKROTIK_SSL_VERIFY
        self.timeout = timeout
        self._base_url = f"https://{self.host}:{self.port}/rest/"
        self._session = requests.Session()
        self._session.auth = (username, password)
        self._session.verify = self.ssl_verify
        self._session.headers.update({"Content-Type": "application/json"})

    # ── Public HTTP helpers ────────────────────────────────────────────────────

    def get(self, path: str, params: dict | None = None) -> Any:
        """Perform a GET request and return parsed JSON."""
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict | None = None) -> Any:
        """Perform a POST request and return parsed JSON."""
        return self._request("POST", path, json=json)

    def put(self, path: str, json: dict | None = None) -> Any:
        """Perform a PUT request and return parsed JSON."""
        return self._request("PUT", path, json=json)

    def patch(self, path: str, json: dict | None = None) -> Any:
        """Perform a PATCH request and return parsed JSON."""
        return self._request("PATCH", path, json=json)

    def delete(self, path: str) -> None:
        """Perform a DELETE request (no response body expected)."""
        self._request("DELETE", path, expect_json=False)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _build_url(self, path: str) -> str:
        # Strip leading slash to avoid urljoin dropping the base path
        return urljoin(self._base_url, path.lstrip("/"))

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: dict | None = None,
        expect_json: bool = True,
    ) -> Any:
        url = self._build_url(path)
        logger.debug("[MikroTik] %s %s params=%s body=%s", method, url, params, json)

        try:
            response = self._session.request(
                method,
                url,
                params=params,
                json=json,
                timeout=self.timeout,
            )
        except requests.ConnectionError as exc:
            raise MikroTikConnectionError(
                f"Cannot connect to router at {self.host}:{self.port}"
            ) from exc
        except requests.Timeout as exc:
            raise MikroTikConnectionError(
                f"Request timed out connecting to {self.host}:{self.port}"
            ) from exc

        self._raise_for_status(response)

        if not expect_json or response.status_code == 204:
            return None

        return response.json()

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        """Map MikroTik HTTP error codes to service exceptions."""
        if response.status_code == 401:
            raise MikroTikAuthError("Invalid MikroTik credentials (HTTP 401).")
        if response.status_code == 403:
            raise MikroTikAuthError("Access forbidden on MikroTik device (HTTP 403).")
        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise MikroTikAPIError(
                f"MikroTik API error: {detail}",
                status_code=response.status_code,
            )
