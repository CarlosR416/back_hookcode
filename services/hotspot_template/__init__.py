"""
Hotspot template renderer service.

Design (OCP / DIP)
------------------
- `BaseTemplateRenderer` defines the interface every vendor renderer must honour.
- `MikroTikTemplateRenderer` implements MikroTik-specific preview/download logic.
- `HotspotTemplateRendererFactory` picks the right renderer for a given vendor
  WITHOUT callers knowing which renderer they get (DIP).

Adding a new vendor = implement BaseTemplateRenderer + register in the factory.
No existing code changes.
"""

from __future__ import annotations

import io
import zipfile
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from jinja2 import Environment, StrictUndefined, Undefined

if TYPE_CHECKING:
    from apps.hotspot.models import HotspotTemplate, HotspotTemplateFile


# ---------------------------------------------------------------------------
# Base interface
# ---------------------------------------------------------------------------


class BaseTemplateRenderer(ABC):
    """
    Contract every vendor renderer must satisfy.

    render_preview(template, file, overrides) → rendered HTML string for browser display.
    render_download(template, file, overrides) → raw content string ready for device upload.
    build_zip(template, overrides)            → bytes of a ZIP archive with all files.
    """

    @abstractmethod
    def render_preview(
        self,
        template: "HotspotTemplate",
        file: "HotspotTemplateFile",
        overrides: dict | None = None,
    ) -> str:
        """Render a single file for in-browser preview."""

    @abstractmethod
    def render_download(
        self,
        template: "HotspotTemplate",
        file: "HotspotTemplateFile",
        overrides: dict | None = None,
    ) -> str:
        """Render a single file ready for device upload."""

    @abstractmethod
    def build_zip(
        self,
        template: "HotspotTemplate",
        overrides: dict | None = None,
    ) -> bytes:
        """Return a ZIP archive containing all template files rendered for download."""


# ---------------------------------------------------------------------------
# MikroTik renderer
# ---------------------------------------------------------------------------

# Dummy values injected in preview mode so MikroTik variables render as readable text.
# MikroTik uses $(variable) syntax in its portal; we replace them with placeholders
# before feeding the content to Jinja2, so the Jinja2 engine never sees them.
_MIKROTIK_PREVIEW_STUBS: dict[str, str] = {
    "$(username)": "demo_user",
    "$(link-login)": "#login",
    "$(link-login-only)": "#login-only",
    "$(link-logout)": "#logout",
    "$(link-status)": "#status",
    "$(error)": "Wrong username or password",
    "$(error-orig)": "Wrong username or password",
    "$(chap-id)": "1",
    "$(chap-challenge)": "aabbccddeeff",
    "$(popup-login)": "false",
    "$(trial)": "0",
    "$(req-username)": "1",
    "$(req-password)": "1",
    "$(mac)": "AA:BB:CC:DD:EE:FF",
    "$(ip)": "192.168.88.100",
    "$(interface)": "wlan1",
}


def _stub_mikrotik_vars(content: str, mode: str) -> str:
    """
    Replace MikroTik $(variable) tokens.

    preview  → human-readable stub values (defined in _MIKROTIK_PREVIEW_STUBS).
    download → leave tokens intact so the router can substitute them at runtime.
    """
    if mode == "download":
        return content
    result = content
    for token, stub in _MIKROTIK_PREVIEW_STUBS.items():
        result = result.replace(token, stub)
    return result


def _build_jinja2_context(template: "HotspotTemplate", overrides: dict | None) -> dict:
    """Merge default template variables with per-request overrides."""
    ctx = dict(template.variables or {})
    if overrides:
        ctx.update(overrides)
    return ctx


def _render_jinja2(content: str, context: dict, strict: bool = False) -> str:
    """
    Render *content* as a Jinja2 template with the given *context*.

    strict=True  → StrictUndefined (raises on missing variables — used for download).
    strict=False → Undefined (silently replaces missing vars with '' — used for preview).
    """
    undefined_cls = StrictUndefined if strict else Undefined
    env = Environment(undefined=undefined_cls, autoescape=False)
    tmpl = env.from_string(content)
    return tmpl.render(**context)


class MikroTikTemplateRenderer(BaseTemplateRenderer):
    """
    Renderer for MikroTik hotspot portal templates.

    Preview mode:
    1. Replace MikroTik $(variable) tokens with human-readable stubs.
    2. Render Jinja2 with merged context (template defaults + overrides).
    3. Return the HTML string — the view streams it as text/html.

    Download mode:
    1. Render Jinja2 ONLY (keep $(variable) tokens intact for the router).
    2. Return the raw string — the view sets Content-Type from file.mime_type.
    """

    def render_preview(
        self,
        template: "HotspotTemplate",
        file: "HotspotTemplateFile",
        overrides: dict | None = None,
    ) -> str:
        stubbed = _stub_mikrotik_vars(file.content, mode="preview")
        ctx = _build_jinja2_context(template, overrides)
        return _render_jinja2(stubbed, ctx, strict=False)

    def render_download(
        self,
        template: "HotspotTemplate",
        file: "HotspotTemplateFile",
        overrides: dict | None = None,
    ) -> str:
        # Keep MikroTik variables intact; only process Jinja2 variables.
        ctx = _build_jinja2_context(template, overrides)
        return _render_jinja2(file.content, ctx, strict=True)

    def build_zip(
        self,
        template: "HotspotTemplate",
        overrides: dict | None = None,
    ) -> bytes:
        """Package all template files into a single ZIP for router upload."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file in template.files.order_by("order", "filename"):
                rendered = self.render_download(template, file, overrides)
                zf.writestr(file.filename, rendered)
        buffer.seek(0)
        return buffer.read()


# ---------------------------------------------------------------------------
# Factory (DIP entry point for views)
# ---------------------------------------------------------------------------

_RENDERER_MAP: dict[str, type[BaseTemplateRenderer]] = {
    "mikrotik": MikroTikTemplateRenderer,
}


class HotspotTemplateRendererFactory:
    """
    Return a renderer instance for the given vendor string.

    Usage:
        renderer = HotspotTemplateRendererFactory.for_vendor(template.vendor)
        html = renderer.render_preview(template, file)
    """

    @staticmethod
    def for_vendor(vendor: str) -> BaseTemplateRenderer:
        renderer_cls = _RENDERER_MAP.get(vendor)
        if renderer_cls is None:
            supported = ", ".join(_RENDERER_MAP.keys())
            raise ValueError(
                f"No renderer registered for vendor '{vendor}'. "
                f"Supported vendors: {supported}."
            )
        return renderer_cls()
