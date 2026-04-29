from logistics.models import FinalInvoice, Notification, ProformaInvoice


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

    notifications = list(request.user.notifications.all()[:6])
    unread_qs = request.user.notifications.filter(is_read=False)
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

    def _module_for(notification):
        link = (notification.link or "").lower()
        category = (notification.category or "").lower()

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

    for notification in unread_qs.only("category", "link"):
        module_key = _module_for(notification)
        if module_key in module_counts:
            module_counts[module_key] += 1

    from logistics.views import _can_switch_lane, _lane_label

    active_lane = _shell_resolve_lane(request)
    return {
        "shell_notifications": notifications,
        "shell_notifications_unread_count": unread_count,
        "shell_module_notification_counts": module_counts,
        "shell_proforma_count_logistics": ProformaInvoice.objects.filter(
            loading__isnull=False
        ).count(),
        "shell_proforma_count_sourcing": ProformaInvoice.objects.filter(
            loading__isnull=True
        ).count(),
        "shell_final_invoice_count_logistics": FinalInvoice.objects.filter(
            loading__isnull=False
        ).count(),
        "shell_final_invoice_count_sourcing": FinalInvoice.objects.filter(
            loading__isnull=True
        ).count(),
        "shell_active_lane": active_lane,
        "shell_active_lane_label": _lane_label(active_lane),
        "shell_can_switch_lane": _can_switch_lane(request.user),
    }
