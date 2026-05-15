"""Role-based access decorators for module permissions."""

from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .role_permissions import role_in_allowed_roles


def role_required(*allowed_roles):
    """Allow access only to users with one of the supplied roles."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect("login")
            if user.is_superuser:
                return view_func(request, *args, **kwargs)
            if not role_in_allowed_roles(user, allowed_roles):
                messages.error(
                    request, "You do not have permission to access this module."
                )
                return redirect("dashboard")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def finance_required(view_func):
    return role_required("FINANCE", "ADMIN")(view_func)


def director_required(view_func):
    return role_required("DIRECTOR", "ADMIN")(view_func)


def procurement_required(view_func):
    return role_required("PROCUREMENT", "DIRECTOR", "ADMIN")(view_func)
