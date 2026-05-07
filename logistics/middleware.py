"""Authentication and role-based middleware guards."""

from django.conf import settings
from django.http import HttpResponseForbidden
from django.http import JsonResponse
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import resolve_url
from urllib.parse import urlsplit

ROLE_ALIASES = {
    "superuser": "ADMIN",
    "data_entry": "OFFICE_ADMIN",
}


def _normalized_role(user):
    return ROLE_ALIASES.get(getattr(user, "role", ""), getattr(user, "role", ""))


class AuthenticationRequiredMiddleware:
    """Require login for every app endpoint except explicitly public routes."""

    PUBLIC_PREFIXES = (
        "/login/",
        "/logout/",
        "/track/",
        "/static/",
        "/admin/",
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

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        if request.user.is_superuser:
            return self.get_response(request)

        role = _normalized_role(request.user)
        path = request.path

        if path.startswith("/sourcing/") and role not in {"PROCUREMENT", "ADMIN"}:
            return HttpResponseForbidden(
                "Procurement role required for sourcing module."
            )

        if path.startswith("/payments/") and role not in {"FINANCE", "ADMIN"}:
            return HttpResponseForbidden("Finance role required for finance module.")

        if path.startswith("/reports/") and role not in {"DIRECTOR", "ADMIN"}:
            return HttpResponseForbidden("Director role required for reports module.")

        if path in {"/login/", "/logout/"}:
            return self.get_response(request)

        return self.get_response(request)


class NotificationTargetReadMiddleware:
    """Clear unread notification badges when the linked target page is opened."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and request.method in {"GET", "HEAD"}
            and not request.path.startswith("/notifications/")
        ):
            self._mark_matching_notifications_read(request)
        return self.get_response(request)

    def _mark_matching_notifications_read(self, request):
        from logistics.models import Notification

        ids_to_mark = []
        current_path = request.path
        current_full_path = request.get_full_path()
        unread_notifications = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).only("id", "link")[:250]
        for notification in unread_notifications:
            link = (notification.link or "").strip()
            if not link:
                continue
            link_parts = urlsplit(link)
            link_path = link_parts.path or link
            link_full_path = link_path
            if link_parts.query:
                link_full_path = f"{link_path}?{link_parts.query}"
            if link_path == current_path or link_full_path == current_full_path:
                ids_to_mark.append(notification.id)
        if ids_to_mark:
            Notification.objects.filter(id__in=ids_to_mark).update(is_read=True)
