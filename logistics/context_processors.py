from django.db.models import Count, Q

from logistics.models import FinalInvoice, Notification, ProformaInvoice

SHELL_MODULE_BADGE_SCAN_LIMIT = 250


def _shell_resolve_lane(request):
    """Resolve the active lane for shell/nav context (mirrors views._resolve_lane)."""
    from logistics.views import _user_default_lane, _can_switch_lane

    user = request.user
    default_lane = _user_default_lane(user)
    privileged = _can_switch_lane(user)
    session_lane = (request.session.get("active_lane") or "").lower()
    if session_lane in {"all", "logistics", "sourcing"}:
        if privileged or session_lane == default_lane:
            return session_lane
    return default_lane


def logistics_shell_context(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}

    notification_qs = request.user.notifications.all()
    notifications = list(
        notification_qs.only("title", "message", "link", "is_read", "created_at")[:6]
    )
    unread_qs = notification_qs.filter(is_read=False)
    unread_count = unread_qs.count()

    module_counts = {
        "transactions": 0,
        "documents": 0,
        "sourcing": 0,
        "suppliers": 0,
        "inventory": 0,
        "fulfillment": 0,
        "invoicing": 0,
        "purchase_orders": 0,
        "trade_payments": 0,
        "receipts": 0,
        "cargo": 0,
        "transit": 0,
        "containers": 0,
        "freight_payments": 0,
        "reports": 0,
        "users": 0,
        "audit": 0,
    }

    def _module_for(category, link):
        link = (link or "").lower()
        category = (category or "").lower()

        if "/invoicing/" in link or category == "invoice":
            return "invoicing"
        if "/purchase-orders/" in link:
            return "purchase_orders"
        if "/fulfillment/" in link:
            return "fulfillment"
        if "/inventory/" in link:
            return "inventory"
        if "/suppliers/" in link:
            return "suppliers"
        if "/sourcing/payments/" in link:
            return "trade_payments"
        if "/receipts/" in link:
            return "receipts"
        if "/sourcing/" in link:
            return "sourcing"
        if "/document-archive/" in link or category == "document":
            return "documents"
        if "/transactions/" in link:
            return "transactions"
        if "/loadings/" in link:
            return "cargo"
        if "/transit/" in link:
            return "transit"
        if "/containers/" in link:
            return "containers"
        if "/payments/" in link:
            return "freight_payments"
        if "/reports/" in link:
            return "reports"
        if "/users/" in link:
            return "users"
        if "/audit/" in link:
            return "audit"
        return None

    unread_badge_rows = unread_qs.values_list("category", "link")[
        :SHELL_MODULE_BADGE_SCAN_LIMIT
    ]
    for category, link in unread_badge_rows:
        module_key = _module_for(category, link)
        if module_key in module_counts:
            module_counts[module_key] += 1

    from logistics.views import _can_switch_lane, _lane_label

    active_lane = _shell_resolve_lane(request)
    proforma_counts = ProformaInvoice.objects.aggregate(
        logistics=Count("id", filter=Q(loading__isnull=False)),
        sourcing=Count("id", filter=Q(loading__isnull=True)),
    )
    final_invoice_counts = FinalInvoice.objects.aggregate(
        logistics=Count("id", filter=Q(loading__isnull=False)),
        sourcing=Count("id", filter=Q(loading__isnull=True)),
    )
    return {
        "shell_notifications": notifications,
        "shell_notifications_unread_count": unread_count,
        "shell_module_notification_counts": module_counts,
        "shell_proforma_count_logistics": proforma_counts["logistics"],
        "shell_proforma_count_sourcing": proforma_counts["sourcing"],
        "shell_final_invoice_count_logistics": final_invoice_counts["logistics"],
        "shell_final_invoice_count_sourcing": final_invoice_counts["sourcing"],
        "shell_active_lane": active_lane,
        "shell_active_lane_label": _lane_label(active_lane),
        "shell_can_switch_lane": _can_switch_lane(request.user),
    }
