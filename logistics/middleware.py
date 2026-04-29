"""Role-based middleware guards for module URL namespaces."""

from django.http import HttpResponseForbidden
from django.shortcuts import redirect


ROLE_ALIASES = {
    "superuser": "ADMIN",
    "data_entry": "OFFICE_ADMIN",
}


def _normalized_role(user):
    return ROLE_ALIASES.get(getattr(user, "role", ""), getattr(user, "role", ""))


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
