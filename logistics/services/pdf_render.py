"""HTML-to-PDF rendering helper.

Renders Django templates straight to PDF using xhtml2pdf so that downloadable
PDFs match the on-screen print previews. xhtml2pdf has limited CSS support
(no flexbox/grid), so the templates under ``logistics/templates/logistics/pdf/``
are written with table-based layouts.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from xhtml2pdf import pisa


def _link_callback(uri: str, rel: str) -> str:  # pragma: no cover - thin
    """Map static/media URIs used in the rendered HTML back to disk paths.

    xhtml2pdf calls this for every ``<img src>`` and CSS url(...) it sees.
    """
    static_url = settings.STATIC_URL or "/static/"
    media_url = settings.MEDIA_URL or "/media/"

    if uri.startswith(static_url):
        path = Path(settings.STATIC_ROOT or "") / uri[len(static_url) :]
        if path.exists():
            return str(path)
        # Fallback: search app static dirs in development
        for app_static in (Path(settings.BASE_DIR) / "logistics" / "static",):
            candidate = app_static / uri[len(static_url) :]
            if candidate.exists():
                return str(candidate)
    if uri.startswith(media_url):
        path = Path(settings.MEDIA_ROOT) / uri[len(media_url) :]
        if path.exists():
            return str(path)
    if uri.startswith(("http://", "https://", "file://")):
        return uri
    # Bare relative path
    candidate = Path(settings.BASE_DIR) / uri.lstrip("/")
    if candidate.exists():
        return str(candidate)
    return uri


def render_to_pdf(template_name: str, context: dict) -> bytes:
    """Render the given Django template to a PDF byte string."""
    html = render_to_string(template_name, context)
    buffer = BytesIO()
    pisa_status = pisa.CreatePDF(
        src=html,
        dest=buffer,
        encoding="utf-8",
        link_callback=_link_callback,
    )
    if pisa_status.err:
        # Fall back to a minimal error page instead of crashing the request.
        buffer = BytesIO()
        pisa.CreatePDF(
            src=f"<html><body><pre>PDF render error: {pisa_status.err}</pre></body></html>",
            dest=buffer,
            encoding="utf-8",
        )
    return buffer.getvalue()
