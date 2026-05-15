"""Shared role permission helpers."""

ROLE_ALIASES = {
    "superuser": "ADMIN",
    "data_entry": "OFFICE_ADMIN",
}

PROCUREMENT_STAFF_ROLES = {"PROCUREMENT", "OFFICE_ADMIN"}
PROCUREMENT_PERMISSION_ROLES = {"PROCUREMENT", "OFFICE_ADMIN", "DIRECTOR", "ADMIN"}


def normalized_role(user):
    role = getattr(user, "role", user or "")
    return ROLE_ALIASES.get(role, role)


def expand_allowed_roles(allowed_roles):
    return set(allowed_roles)


def role_in_allowed_roles(user, allowed_roles):
    if getattr(user, "is_superuser", False):
        return True
    return normalized_role(user) in expand_allowed_roles(allowed_roles)


def role_has_procurement_permissions(user):
    return role_in_allowed_roles(user, PROCUREMENT_PERMISSION_ROLES)
