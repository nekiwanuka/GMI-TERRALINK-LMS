"""Authentication and role-based middleware guards."""

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.http import JsonResponse
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import resolve_url
from urllib.parse import urlsplit

from .role_permissions import PROCUREMENT_PERMISSION_ROLES, normalized_role


def _normalized_path(value):
    path = urlsplit(value or "").path or "/"
    if path != "/":
        path = path.rstrip("/")
    return path


def _record_key(path):
    segments = [segment for segment in _normalized_path(path).split("/") if segment]
    record_segments = {
        "clients",
        "container-returns",
        "documents",
        "final",
        "fulfillment",
        "inventory",
        "loadings",
        "payments",
        "pod",
        "proformas",
        "purchase-orders",
        "receipts",
        "sourcing",
        "supplier-payments",
        "suppliers",
        "transactions",
        "transit",
    }
    for index, segment in enumerate(segments[:-1]):
        if segment in record_segments and segments[index + 1].isdigit():
            return segment, segments[index + 1]
    return None


def _paths_match_notification_target(notification_link, current_path):
    link_path = _normalized_path(notification_link)
    current_path = _normalized_path(current_path)
    if link_path == current_path:
        return True
    if current_path.startswith(f"{link_path}/"):
        return True
    link_key = _record_key(link_path)
    current_key = _record_key(current_path)
    return bool(link_key and link_key == current_key)


class FreshAuthenticatedPageMiddleware:
    """Prevent stale authenticated HTML screens from being reused by browsers."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return response
        if request.method not in {"GET", "HEAD"}:
            return response
        if request.path.startswith(("/static/", "/media/")):
            return response
        if "text/html" not in response.get("Content-Type", ""):
            return response
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response


class AuthenticationRequiredMiddleware:
    """Require login for every app endpoint except explicitly public routes."""

    PUBLIC_PREFIXES = (
        "/login/",
        "/logout/",
        "/track/",
        "/static/",
        "/administrator/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated or self._is_public_path(request.path):
            return self.get_response(request)

        if request.path.startswith("/api/"):
            return JsonResponse({"detail": "Authentication required."}, status=401)

        return redirect_to_login(
            request.get_full_path(), resolve_url(settings.LOGIN_URL)
        )

    def _is_public_path(self, path):
        static_url = getattr(settings, "STATIC_URL", "/static/")
        public_prefixes = self.PUBLIC_PREFIXES
        if static_url and static_url not in public_prefixes:
            public_prefixes = public_prefixes + (static_url,)
        return any(path.startswith(prefix) for prefix in public_prefixes)


class ModuleRoleMiddleware:
    """Apply module-level role checks by URL prefix."""

    DOCUMENT_READ_PREFIXES = (
        "/sourcing/invoicing/proformas/",
        "/sourcing/invoicing/final/",
    )

    DOCUMENT_READ_SUFFIXES = (
        "/invoice/",
        "/receipt/",
        "/pdf/",
        "/html-preview/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        role = normalized_role(request.user)
        path = request.path

        if self._is_document_read_path(request):
            return self.get_response(request)

        if path.startswith("/administrator/") and role != "ADMIN":
            return HttpResponseForbidden("System Admin access required.")

        if path.startswith("/api/") and role != "ADMIN":
            if request.headers.get("accept", "").startswith("application/json"):
                return JsonResponse(
                    {"detail": "System Admin access required."}, status=403
                )
            return HttpResponseForbidden("System Admin access required.")

        if request.user.is_superuser:
            return self.get_response(request)

        if path.startswith("/sourcing/") and role not in PROCUREMENT_PERMISSION_ROLES:
            return HttpResponseForbidden(
                "Procurement role required for sourcing module."
            )

        if path.startswith("/payments/") and role not in {
            "FINANCE",
            "DIRECTOR",
            "ADMIN",
            "OFFICE_ADMIN",
        }:
            return HttpResponseForbidden("Finance role required for finance module.")

        if path.startswith("/reports/") and role not in {
            "DIRECTOR",
            "FINANCE",
            "ADMIN",
            "OFFICE_ADMIN",
        }:
            return HttpResponseForbidden("Director role required for reports module.")

        if path in {"/login/", "/logout/"}:
            return self.get_response(request)

        return self.get_response(request)

    def _is_document_read_path(self, request):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            return False
        path = request.path
        if any(path.startswith(prefix) for prefix in self.DOCUMENT_READ_PREFIXES):
            return True
        if path.startswith("/payments/") and any(
            path.endswith(suffix) for suffix in self.DOCUMENT_READ_SUFFIXES
        ):
            return True
        return False


class NotificationTargetReadMiddleware:
    """Clear unread notification badges when the linked target page is opened."""

    SKIP_PREFIXES = (
        "/administrator/",
        "/api/",
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and request.method in {"GET", "HEAD"}
            and not request.path.startswith("/notifications/")
            and not request.path.startswith(self.SKIP_PREFIXES)
        ):
            self._mark_matching_notifications_read(request)
        return self.get_response(request)

    def _mark_matching_notifications_read(self, request):
        from logistics.models import Notification

        ids_to_mark = []
        current_path = request.path
        current_full_path = request.get_full_path()
        unread_count_cache_key = f"notification-unread-count:{request.user.pk}"
        cached_unread_count = cache.get(unread_count_cache_key)
        if cached_unread_count == 0:
            return
        unread_notifications = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).only("id", "link")[:250]
        checked_any = False
        for notification in unread_notifications:
            checked_any = True
            link = (notification.link or "").strip()
            if not link:
                continue
            link_parts = urlsplit(link)
            link_path = link_parts.path or link
            link_full_path = link_path
            if link_parts.query:
                link_full_path = f"{link_path}?{link_parts.query}"
            if link_full_path == current_full_path or _paths_match_notification_target(
                link_path, current_path
            ):
                ids_to_mark.append(notification.id)
        if ids_to_mark:
            Notification.objects.filter(id__in=ids_to_mark).update(is_read=True)
            cache.delete(unread_count_cache_key)
        elif not checked_any:
            cache.set(unread_count_cache_key, 0, 30)
