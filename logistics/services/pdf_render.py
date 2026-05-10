"""HTML-to-PDF rendering helper.

Browser rendering is preferred so downloads match print previews. Shared hosts
often cannot run Chromium or install native HTML-to-PDF libraries, so this
module must keep every server-side renderer optional at import time.
"""

from __future__ import annotations

import importlib
from io import BytesIO
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from django.conf import settings
from django.template.loader import render_to_string

_WEASYPRINT_HTML = None
_WEASYPRINT_CHECKED = False


def _weasyprint_html_class():
    """Return WeasyPrint's HTML class when the host has its runtime libraries."""
    global _WEASYPRINT_CHECKED, _WEASYPRINT_HTML
    if _WEASYPRINT_CHECKED:
        return _WEASYPRINT_HTML
    _WEASYPRINT_CHECKED = True
    try:  # pragma: no cover - depends on host system libraries
        _WEASYPRINT_HTML = importlib.import_module("weasyprint").HTML
    except (ImportError, OSError):  # pragma: no cover - production fallback path
        _WEASYPRINT_HTML = None
    return _WEASYPRINT_HTML


def _resolve_local_asset(uri: str) -> str:
    """Resolve static/media URLs to file URIs for browser-based PDF rendering."""
    static_url = settings.STATIC_URL or "/static/"
    media_url = settings.MEDIA_URL or "/media/"

    candidates = []
    if uri.startswith(static_url):
        relative = uri[len(static_url) :]
        if settings.STATIC_ROOT:
            candidates.append(Path(settings.STATIC_ROOT) / relative)
        candidates.append(Path(settings.BASE_DIR) / "logistics" / "static" / relative)
    elif uri.startswith(media_url):
        candidates.append(Path(settings.MEDIA_ROOT) / uri[len(media_url) :])

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve().as_uri()
    return uri


def _rewrite_assets_for_browser(html: str) -> str:
    """Make local static/media references readable from a temporary HTML file."""
    static_url = re.escape(settings.STATIC_URL or "/static/")
    media_url = re.escape(settings.MEDIA_URL or "/media/")
    asset_pattern = rf"(?:{static_url}|{media_url})[^\"'\)\s]+"

    def replace_css_url(match: re.Match) -> str:
        quote, uri = match.groups()
        return f"url({quote}{_resolve_local_asset(uri)}{quote})"

    html = re.sub(
        rf"((?:src|href)=)([\"'])({asset_pattern})([\"'])",
        lambda match: f"{match.group(1)}{match.group(2)}{_resolve_local_asset(match.group(3))}{match.group(4)}",
        html,
    )
    html = re.sub(
        rf"url\(([\"']?)({asset_pattern})\1\)",
        replace_css_url,
        html,
    )
    return html


def _chromium_executable() -> str | None:
    configured = getattr(settings, "CHROMIUM_EXECUTABLE", "")
    candidates = [
        configured,
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def render_to_pdf(template_name: str, context: dict) -> bytes:
    """Render the given Django template to a PDF byte string."""
    html = _rewrite_assets_for_browser(render_to_string(template_name, context))
    HTML = _weasyprint_html_class()
    if HTML is not None:
        try:
            return HTML(
                string=html,
                base_url=Path(settings.BASE_DIR).resolve().as_uri(),
            ).write_pdf()
        except Exception:  # noqa: BLE001
            pass
    return _render_minimal_pdf(html)


def _render_minimal_pdf(html: str) -> bytes:
    """Return a simple PDF when optional HTML renderers are unavailable."""
    from html import unescape

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    html = re.sub(
        r"<style\b[^>]*>.*?</style>", " ", html, flags=re.IGNORECASE | re.DOTALL
    )
    html = re.sub(
        r"<script\b[^>]*>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL
    )
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</(p|tr|div|h[1-6]|li|table)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", unescape(text))

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    x = 40
    y = height - 44
    pdf.setFont("Helvetica", 9)
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        while line:
            chunk = line[:115]
            pdf.drawString(x, y, chunk)
            line = line[115:]
            y -= 12
            if y < 44:
                pdf.showPage()
                pdf.setFont("Helvetica", 9)
                y = height - 44
    pdf.save()
    return buffer.getvalue()


def render_to_browser_pdf(template_name: str, context: dict) -> bytes:
    """Render a Django template to PDF using Chromium's print engine.

    This is used for documents where the downloadable PDF must closely match
    the browser print preview. If Chromium is unavailable or rendering fails,
    callers still receive the optional server-side fallback output.
    """
    browser = _chromium_executable()
    if not browser:
        return render_to_pdf(template_name, context)

    html = _rewrite_assets_for_browser(render_to_string(template_name, context))
    temp_dir = tempfile.mkdtemp()
    try:
        temp_path = Path(temp_dir)
        html_path = temp_path / "document.html"
        pdf_path = temp_path / "document.pdf"
        profile_path = temp_path / "profile"
        html_path.write_text(html, encoding="utf-8")

        command = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-breakpad",
            "--disable-crash-reporter",
            "--disable-features=Crashpad",
            "--no-pdf-header-footer",
            "--allow-file-access-from-files",
            "--print-to-pdf-no-header",
            f"--user-data-dir={profile_path}",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
            if pdf_path.exists() and pdf_path.stat().st_size > 1000:
                return pdf_path.read_bytes()
        except Exception:  # noqa: BLE001
            pass
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return render_to_pdf(template_name, context)
