"""Views for the logistics management system."""

import csv
import json
import os
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum, ProtectedError, Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .pi_parser import (
    parse_purchase_inquiry,
    items_to_sourcing_lines,
    build_sourcing_notes,
)


def _extract_text_from_file(file_obj):
    """
    Best-effort text extraction from an uploaded file.
    Supports PDF (via pypdf), Word .docx (via python-docx), and plain text.
    Returns extracted text string (may be empty if extraction fails or libs missing).
    """
    filename = file_obj.name.lower()
    extracted = ""
    try:
        if filename.endswith(".pdf"):
            try:
                from pypdf import PdfReader

                file_obj.seek(0)
                reader = PdfReader(file_obj)
                parts = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        parts.append(text)
                extracted = "\n".join(parts)
            except ImportError:
                extracted = "[PDF extraction requires pypdf. Run: pip install pypdf]"
        elif filename.endswith(".docx"):
            try:
                import docx

                file_obj.seek(0)
                document = docx.Document(file_obj)
                extracted = "\n".join(
                    p.text for p in document.paragraphs if p.text.strip()
                )
            except ImportError:
                extracted = "[Word extraction requires python-docx. Run: pip install python-docx]"
        elif filename.endswith(".txt"):
            file_obj.seek(0)
            extracted = file_obj.read().decode("utf-8", errors="replace")
        else:
            extracted = f"[File type not supported for automatic extraction: {os.path.splitext(filename)[1]}]"
    except Exception as exc:  # noqa: BLE001
        extracted = f"[Extraction failed: {exc}]"
    return extracted.strip()


from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .forms import (
    ClientForm,
    ContainerReturnForm,
    DocumentForm,
    FinalInvoiceForm,
    FulfillmentLineForm,
    FulfillmentOrderForm,
    InventoryItemForm,
    LoadingForm,
    PaymentForm,
    PaymentTransactionForm,
    ProformaInvoiceForm,
    ProofOfDeliveryForm,
    ShipmentLegForm,
    SourcingForm,
    SupplierForm,
    SupplierPaymentForm,
    SupplierProductForm,
    TransactionForm,
    TransitForm,
    TransactionPaymentRecordForm,
    UserRegistrationForm,
)
from .decorators import (
    director_required,
    finance_required,
    procurement_required,
    role_required,
)
from .models import (
    _draw_international_terms_footer,
    _draw_standard_doc_header,
    AuditLog,
    Client,
    ContainerReturn,
    CustomUser,
    Document,
    DocumentArchive,
    FinalInvoice,
    FulfillmentLine,
    FulfillmentOrder,
    InventoryItem,
    Loading,
    Notification,
    Payment,
    PaymentTransaction,
    ProformaInvoice,
    ProofOfDelivery,
    PurchaseOrder,
    Receipt,
    Sourcing,
    Supplier,
    SupplierPayment,
    SupplierProduct,
    ShipmentLeg,
    Transaction,
    TransactionPaymentRecord,
    Transit,
)
from .services import (
    WorkflowTransitionError,
    transition_cargo_item,
    transition_shipment,
)
from .services.reporting import DirectorReportingService


DEFAULT_PAGE_SIZE = 20
AUDIT_PAGE_SIZE = 40


def _notify_roles(*, title, message, link="", category="system", roles=None):
    roles = roles or ["ADMIN", "DIRECTOR", "FINANCE", "PROCUREMENT"]
    recipients = CustomUser.objects.filter(is_active=True).filter(
        Q(is_superuser=True) | Q(role__in=roles)
    )
    Notification.objects.bulk_create(
        [
            Notification(
                recipient=recipient,
                title=title,
                message=message,
                link=link,
                category=category,
            )
            for recipient in recipients.distinct()
        ]
    )


def _redirect_back(request, default="dashboard"):
    """Redirect to the referring page when possible, else use a safe fallback."""
    target = request.META.get("HTTP_REFERER")
    if target:
        return redirect(target)
    return redirect(default)


def _user_default_lane(user):
    role = getattr(user, "role", "")
    if getattr(user, "is_superuser", False) or role in {"ADMIN", "DIRECTOR", "FINANCE"}:
        return "all"
    if role == "PROCUREMENT":
        return "sourcing"
    return "logistics"


def _resolve_lane(request):
    # Honour an explicit ?lane= override and persist it to the session
    requested_lane = (request.GET.get("lane") or "").strip().lower()
    default_lane = _user_default_lane(request.user)
    privileged = request.user.is_superuser or getattr(request.user, "role", "") in {
        "ADMIN",
        "DIRECTOR",
        "FINANCE",
    }
    if requested_lane in {"all", "logistics", "sourcing"}:
        if privileged or requested_lane == default_lane:
            request.session["active_lane"] = requested_lane
            return requested_lane
    # Fall back to session, then role default
    session_lane = (request.session.get("active_lane") or "").lower()
    if session_lane in {"all", "logistics", "sourcing"}:
        if privileged or session_lane == default_lane:
            return session_lane
    return default_lane


def _path_lane(request):
    path = (request.path or "").lower()
    if path.startswith("/logistics/"):
        return "logistics"
    if path.startswith("/sourcing/"):
        return "sourcing"
    return None


def _resolve_lane_with_path(request):
    forced_lane = _path_lane(request)
    if forced_lane in {"logistics", "sourcing"}:
        default_lane = _user_default_lane(request.user)
        if _can_switch_lane(request.user) or forced_lane == default_lane:
            request.session["active_lane"] = forced_lane
            return forced_lane
    return _resolve_lane(request)


def _invoice_lane_from_loading_id(loading_id):
    return "logistics" if loading_id else "sourcing"


def _proforma_route_name(proforma, action):
    lane = _invoice_lane_from_loading_id(proforma.loading_id)
    return f"{lane}_proforma_{action}"


def _final_invoice_route_name(invoice, action):
    lane = _invoice_lane_from_loading_id(invoice.loading_id)
    return f"{lane}_final_invoice_{action}"


def _canonical_route_redirect(request, route_name, **kwargs):
    current_route = request.resolver_match.url_name if request.resolver_match else ""
    if current_route != route_name:
        return redirect(route_name, **kwargs)
    return None


def _lane_label(lane):
    labels = {
        "all": "All operations",
        "logistics": "Logistics",
        "sourcing": "Sourcing / Trade",
    }
    return labels.get(lane, "All operations")


def _can_switch_lane(user):
    return user.is_superuser or getattr(user, "role", "") in {
        "ADMIN",
        "DIRECTOR",
        "FINANCE",
    }


def _apply_transaction_lane(queryset, lane):
    if lane == "logistics":
        return queryset.filter(source_loading__isnull=False)
    if lane == "sourcing":
        return queryset.filter(source_loading__isnull=True)
    return queryset


def _apply_loading_lane(queryset, lane):
    if lane == "sourcing":
        return queryset.none()
    return queryset


def _apply_client_lane(queryset, lane):
    if lane == "logistics":
        return queryset.filter(
            Q(loadings__isnull=False) | Q(transactions__source_loading__isnull=False)
        ).distinct()
    if lane == "sourcing":
        return queryset.filter(transactions__source_loading__isnull=True).distinct()
    return queryset


def _apply_payment_lane(queryset, lane):
    if lane == "sourcing":
        return queryset.none()
    return queryset


def _apply_sourcing_lane(queryset, lane):
    if lane == "logistics":
        return queryset.none()
    return queryset


def _apply_inventory_lane(queryset, lane):
    if lane == "logistics":
        return queryset.none()
    return queryset


def _apply_proforma_lane(queryset, lane):
    if lane == "logistics":
        return queryset.filter(loading__isnull=False)
    if lane == "sourcing":
        return queryset.filter(loading__isnull=True)
    return queryset


def _apply_final_invoice_lane(queryset, lane):
    if lane == "logistics":
        return queryset.filter(loading__isnull=False)
    if lane == "sourcing":
        return queryset.filter(loading__isnull=True)
    return queryset


def _apply_fulfillment_lane(queryset, lane):
    if lane == "logistics":
        return queryset.filter(transaction__source_loading__isnull=False)
    if lane == "sourcing":
        return queryset.filter(transaction__source_loading__isnull=True)
    return queryset


def _latest_final_invoice_for_client(client):
    return (
        FinalInvoice.objects.filter(transaction__customer=client)
        .order_by("-is_confirmed", "-created_at")
        .first()
    )


def _build_loading_proforma_items(loading):
    if loading.entry_type == "GROUPAGE":
        cbm = float(loading.cbm) if loading.cbm else 0.0
        return [
            {
                "description": "Sea Freight – Groupage (LCL)",
                "quantity": str(cbm) if cbm else "0",
                "unit": "CBM",
                "unit_price": 0.0,
                "sales_price": 0.0,
                "total": 0.0,
            }
        ]
    else:
        container_label = (
            loading.get_container_size_display() if loading.container_size else "FCL"
        )
        return [
            {
                "description": f"Sea Freight – Full Container ({container_label})",
                "quantity": "1",
                "unit": "Container",
                "unit_price": 0.0,
                "sales_price": 0.0,
                "total": 0.0,
            }
        ]


def _ensure_transaction_for_loading(loading, *, created_by):
    existing_transaction = getattr(loading, "source_transaction", None)
    if existing_transaction:
        return existing_transaction, False

    transaction_record = Transaction.objects.create(
        customer=loading.client,
        source_loading=loading,
        status="RECEIVED",
        description=(loading.item_description or f"Cargo {loading.loading_id}").strip(),
        notes=(
            f"Auto-generated from cargo {loading.loading_id} | "
            f"Route: {loading.origin} -> {loading.destination}"
        ),
        created_by=created_by,
    )
    return transaction_record, True


def _ensure_proforma_for_loading(loading, *, created_by):
    transaction_record, transaction_created = _ensure_transaction_for_loading(
        loading, created_by=created_by
    )
    existing_proforma = transaction_record.proforma_invoices.order_by(
        "-created_at"
    ).first()
    if existing_proforma:
        return transaction_record, existing_proforma, transaction_created, False

    proforma = ProformaInvoice.objects.create(
        transaction=transaction_record,
        loading=loading,
        items=_build_loading_proforma_items(loading),
        subtotal=Decimal("0.00"),
        sourcing_fee=Decimal("0.00"),
        handling_fee=Decimal("0.00"),
        shipping_fee=Decimal("0.00"),
        validity_date=timezone.localdate() + timedelta(days=30),
        status="DRAFT",
        created_by=created_by,
    )
    Transaction.objects.filter(
        pk=transaction_record.pk,
        status__in=["RECEIVED", "CLEANED", "SENT_TO_SOURCING", "QUOTED"],
    ).update(status="PROFORMA_CREATED")
    transaction_record.status = "PROFORMA_CREATED"
    return transaction_record, proforma, transaction_created, True


def _ensure_freight_invoice_for_loading(loading, *, created_by):
    existing_payment = Payment.objects.filter(loading=loading).first()
    if existing_payment:
        return existing_payment, False

    final_invoice = _latest_final_invoice_for_client(loading.client)
    payment = Payment.objects.create(
        loading=loading,
        final_invoice=final_invoice,
        billing_basis="manual",
        billing_rate=None,
        amount_charged=Decimal("0.00"),
        amount_paid=Decimal("0.00"),
        balance=Decimal("0.00"),
        created_by=created_by,
    )
    return payment, True


def _apply_transaction_status_badge(transaction, *, sourcing_entry_count=0):
    transaction.list_status_display = transaction.get_status_display()
    transaction.list_status_class = "bg-dark"
    if transaction.status == "SENT_TO_SOURCING":
        if sourcing_entry_count:
            transaction.list_status_display = "In Sourcing Review"
            transaction.list_status_class = "bg-info text-dark"
        else:
            transaction.list_status_display = "Awaiting Sourcing Intake"
            transaction.list_status_class = "bg-warning text-dark"
    return transaction


def _resolve_sourcing_owner(preferred_user=None):
    if (
        preferred_user
        and preferred_user.is_active
        and (
            preferred_user.is_superuser
            or preferred_user.role in {"PROCUREMENT", "ADMIN"}
        )
    ):
        return preferred_user
    return (
        CustomUser.objects.filter(is_active=True)
        .filter(Q(is_superuser=True) | Q(role__in=["PROCUREMENT", "ADMIN"]))
        .order_by("is_superuser", "id")
        .first()
    )


def _ensure_sourcing_entry_for_transaction(
    transaction, *, preferred_user=None, pi_document=None
):
    existing_sourcing = (
        Sourcing.objects.filter(transaction=transaction)
        .order_by("-updated_at", "-created_at")
        .first()
    )
    if existing_sourcing:
        return existing_sourcing, False

    sourcing_owner = _resolve_sourcing_owner(preferred_user)
    if not sourcing_owner:
        return None, False

    structured_data = (pi_document.structured_data or {}) if pi_document else {}
    sourcing_record = Sourcing.objects.create(
        transaction=transaction,
        supplier_name="Pending supplier assignment",
        supplier_contact="",
        item_details=(
            items_to_sourcing_lines(structured_data) if structured_data else []
        ),
        unit_prices={},
        notes=(
            build_sourcing_notes(structured_data)
            if structured_data
            else "Initial sourcing intake created from client PI."
        ),
        created_by=sourcing_owner,
    )
    return sourcing_record, True


# ===== AUTHENTICATION =====


def login_view(request):
    """Authenticate user credentials and start a session."""
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("dashboard")
        messages.error(request, "Invalid username or password")
    return render(request, "logistics/login.html")


def logout_view(request):
    """Terminate an authenticated session."""
    logout(request)
    messages.success(request, "Logged out successfully")
    return redirect("login")


@login_required
def set_lane(request):
    """Persist the user's chosen department lane to the session."""
    lane = (request.POST.get("lane") or request.GET.get("lane") or "").strip().lower()
    if lane in {"all", "logistics", "sourcing"}:
        privileged = _can_switch_lane(request.user)
        default = _user_default_lane(request.user)
        if privileged or lane == default:
            request.session["active_lane"] = lane
    next_url = (
        request.POST.get("next")
        or request.GET.get("next")
        or request.META.get("HTTP_REFERER")
        or "/"
    )
    # Security: only allow relative redirects
    from urllib.parse import urlparse

    parsed = urlparse(next_url)
    if parsed.netloc and parsed.netloc != request.get_host():
        next_url = "/"
    return redirect(next_url)


def register_view(request):
    """Create new user accounts (superusers only)."""
    if not request.user.is_authenticated:
        return redirect("login")
    if not request.user.is_superuser and request.user.role not in {
        "ADMIN",
        "superuser",
    }:
        messages.error(request, "Only superusers can create new users")
        return redirect("dashboard")
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"User {user.username} created successfully")
            log_audit("user", "create", user.id, str(user), request.user)
            return redirect("user_list")
    else:
        form = UserRegistrationForm()
    return render(request, "logistics/register.html", {"form": form})


# ===== DASHBOARD & USERS =====


@login_required
def user_list(request):
    """List all users (superusers only)."""
    if not request.user.is_superuser and request.user.role not in {
        "ADMIN",
        "superuser",
    }:
        messages.error(request, "Permission denied")
        return redirect("dashboard")
    users = CustomUser.objects.all()
    page_obj, query_string, page_range = paginate_queryset(request, users)
    return render(
        request,
        "logistics/users/list.html",
        {
            "users": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "page_range": page_range,
        },
    )


# ===== CLIENT MANAGEMENT =====


@login_required
def client_list(request):
    lane = _resolve_lane(request)
    clients = _apply_client_lane(Client.objects.all(), lane)
    search = request.GET.get("search", "")
    if search:
        clients = clients.filter(
            Q(client_id__icontains=search)
            | Q(name__icontains=search)
            | Q(contact_person__icontains=search)
        )
    page_obj, query_string, page_range = paginate_queryset(request, clients)
    return render(
        request,
        "logistics/clients/list.html",
        {
            "clients": page_obj,
            "search": search,
            "page_obj": page_obj,
            "query_string": query_string,
            "page_range": page_range,
            "active_lane": lane,
            "active_lane_label": _lane_label(lane),
            "can_switch_lane": _can_switch_lane(request.user),
        },
    )


@login_required
def client_create(request):
    if request.method == "POST":
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save(commit=False)
            client.created_by = request.user
            client.save()
            messages.success(request, f"Client {client.name} created successfully")
            log_audit("client", "create", client.id, str(client), request.user)
            return redirect("client_detail", pk=client.id)
    else:
        form = ClientForm()
    return render(
        request,
        "logistics/clients/form.html",
        {"form": form, "title": "Create Client"},
    )


@login_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    return render(
        request,
        "logistics/clients/detail.html",
        {"client": client, "loadings": client.loadings.all()},
    )


@login_required
def client_update(request, pk):
    if not (
        request.user.is_superuser
        or request.user.role in {"DIRECTOR", "ADMIN", "superuser"}
    ):
        messages.error(
            request,
            "Only the Director or System Administrator can edit clients. Please request permission from an authorised user.",
        )
        return redirect("client_detail", pk=pk)
    client = get_object_or_404(Client, pk=pk)
    if request.method == "POST":
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, "Client updated successfully")
            log_audit("client", "update", client.id, str(client), request.user)
            return redirect("client_detail", pk=client.id)
    else:
        form = ClientForm(instance=client)
    return render(
        request,
        "logistics/clients/form.html",
        {"form": form, "title": "Update Client", "client": client},
    )


@login_required
def client_delete(request, pk):
    if not (
        request.user.is_superuser
        or request.user.role in {"DIRECTOR", "ADMIN", "superuser"}
    ):
        messages.error(
            request,
            "Only the Director or System Administrator can delete clients. Please request permission from an authorised user.",
        )
        return redirect("client_detail", pk=pk)
    client = get_object_or_404(Client, pk=pk)
    client_str = str(client)
    client_id = client.id
    try:
        client.delete()
    except ProtectedError:
        messages.error(
            request,
            "This client cannot be deleted while there are cargo/loadings linked to them. Remove or reassign those records first.",
        )
        return redirect("client_detail", pk=client_id)
    messages.success(request, "Client deleted successfully")
    log_audit("client", "delete", client_id, client_str, request.user)
    return redirect("client_list")


# ===== LOADING MANAGEMENT =====


@login_required
def loading_list(request):
    lane = _resolve_lane(request)
    loadings = _apply_loading_lane(Loading.objects.select_related("client"), lane)
    search = request.GET.get("search", "")
    if search:
        loadings = loadings.filter(
            Q(loading_id__icontains=search)
            | Q(client__name__icontains=search)
            | Q(origin__icontains=search)
        )
    closed_filter = request.GET.get("closed")
    if closed_filter == "1":
        loadings = loadings.filter(closed_at__isnull=False)
    elif closed_filter == "0":
        loadings = loadings.filter(closed_at__isnull=True)
    page_obj, query_string, page_range = paginate_queryset(request, loadings)
    return render(
        request,
        "logistics/loadings/list.html",
        {
            "loadings": page_obj,
            "search": search,
            "page_obj": page_obj,
            "query_string": query_string,
            "page_range": page_range,
            "active_lane": lane,
            "active_lane_label": _lane_label(lane),
            "can_switch_lane": _can_switch_lane(request.user),
        },
    )


@login_required
def loading_create(request):
    preset_type = (request.GET.get("type") or "").strip().lower()
    preset_map = {
        "full": "FULL_CONTAINER",
        "full_container": "FULL_CONTAINER",
        "groupage": "GROUPAGE",
        "group": "GROUPAGE",
    }
    preset_entry_type = preset_map.get(preset_type)

    if request.method == "POST":
        form = LoadingForm(request.POST)
        if form.is_valid():
            loading = form.save(commit=False)
            loading.created_by = request.user
            loading.save()
            flow_transaction, proforma, transaction_created, proforma_created = (
                _ensure_proforma_for_loading(loading, created_by=request.user)
            )
            messages.success(
                request, f"Loading {loading.loading_id} created successfully"
            )
            if transaction_created:
                messages.success(
                    request,
                    f"Commercial flow {flow_transaction.transaction_id} was opened automatically for this cargo.",
                )
            if proforma_created:
                messages.success(
                    request,
                    f"Quotation / Proforma draft PI-{proforma.pk} was generated automatically.",
                )
            log_audit("loading", "create", loading.id, str(loading), request.user)
            _notify_roles(
                title="New loading registered",
                message=f"Loading {loading.loading_id} ({loading.client.name}) created.",
                link=f"/loadings/{loading.id}/",
                category="logistics",
                roles=["ADMIN", "DIRECTOR", "FINANCE", "OFFICE_ADMIN"],
            )
            can_manage_commercial_flow = (
                request.user.is_superuser
                or request.user.role
                in {
                    "ADMIN",
                    "DIRECTOR",
                    "FINANCE",
                    "PROCUREMENT",
                }
            )
            if can_manage_commercial_flow:
                return redirect("proforma_update", pk=proforma.id)
            messages.warning(
                request,
                "Cargo was saved and the quotation draft was created. Ask Finance or Procurement to complete the invoicing step.",
            )
            return redirect("loading_detail", pk=loading.id)
    else:
        initial = {"entry_type": preset_entry_type} if preset_entry_type else None
        form = LoadingForm(initial=initial)
    return render(
        request,
        "logistics/loadings/form.html",
        {"form": form, "title": "Create Loading"},
    )


@login_required
def loading_detail(request, pk):
    loading = get_object_or_404(Loading, pk=pk)
    chargeable_wm = loading.chargeable_wm
    flow_transaction = getattr(loading, "source_transaction", None)
    proforma = None
    final_invoice = None
    total_paid = Decimal("0.00")
    balance_due = None

    if flow_transaction:
        proforma = flow_transaction.proforma_invoices.order_by("-created_at").first()
        final_invoice = flow_transaction.final_invoices.order_by("-created_at").first()
        total_paid = flow_transaction.payment_records.aggregate(total=Sum("amount"))[
            "total"
        ] or Decimal("0.00")
        if final_invoice:
            balance_due = max(
                (final_invoice.total_amount or Decimal("0.00")) - total_paid,
                Decimal("0.00"),
            )

    context = {
        "loading": loading,
        "has_transit": hasattr(loading, "transit"),
        "has_payment": hasattr(loading, "payment"),
        "chargeable_wm": chargeable_wm,
        "flow_transaction": flow_transaction,
        "proforma": proforma,
        "final_invoice": final_invoice,
        "total_paid": total_paid,
        "balance_due": balance_due,
    }
    closure_items, closure_ready = evaluate_loading_closure(loading)
    context["closure_items"] = closure_items
    context["closure_ready"] = closure_ready
    return render(request, "logistics/loadings/detail.html", context)


@login_required
def loading_start_flow(request, pk):
    loading = get_object_or_404(Loading, pk=pk)
    _, proforma, _, created = _ensure_proforma_for_loading(
        loading, created_by=request.user
    )
    if created:
        messages.success(
            request,
            f"Quotation / Proforma draft PI-{proforma.pk} was generated for cargo {loading.loading_id}.",
        )
    can_manage_commercial_flow = request.user.is_superuser or request.user.role in {
        "ADMIN",
        "DIRECTOR",
        "FINANCE",
        "PROCUREMENT",
    }
    if not can_manage_commercial_flow:
        messages.warning(
            request,
            "The quotation draft is ready, but only Finance or Procurement can complete invoicing.",
        )
        return redirect("loading_detail", pk=loading.pk)
    return redirect("proforma_update", pk=proforma.pk)


@login_required
def loading_document(request, pk):
    loading = get_object_or_404(Loading.objects.select_related("client"), pk=pk)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 40

    if loading.entry_type == "GROUPAGE":
        title = "GROUPAGE CARGO NOTE"
        reference = loading.groupage_note_number or loading.loading_id
        filename = f"logistics_{loading.loading_id}_groupage_note.pdf"
    else:
        title = "BILL OF LADING"
        reference = loading.bill_of_lading_number or loading.loading_id
        filename = f"logistics_{loading.loading_id}_bill_of_lading.pdf"

    _draw_standard_doc_header(pdf, width, height, title, reference)

    pdf.setFillColor(colors.black)
    top = height - 126
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin, top, "Shipment Reference")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(margin, top - 16, f"Entry Number: {loading.loading_id}")
    pdf.drawString(margin, top - 30, f"Client: {loading.client.name}")
    pdf.drawString(margin, top - 44, f"Entry Type: {loading.get_entry_type_display()}")
    pdf.drawString(
        margin,
        top - 58,
        f"Warehouse: {loading.warehouse_location or '-'}",
    )

    route_top = top - 80
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin, route_top, "Route & Cargo")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(margin, route_top - 16, f"Origin: {loading.origin}")
    pdf.drawString(margin, route_top - 30, f"Destination: {loading.destination}")
    pdf.drawString(
        margin,
        route_top - 44,
        f"Loading Date: {loading.loading_date.strftime('%Y-%m-%d %H:%M')}",
    )
    pdf.drawString(
        margin,
        route_top - 58,
        f"Weight: {loading.weight} KG" if loading.weight else "Weight: -",
    )
    pdf.drawString(
        margin,
        route_top - 72,
        f"CBM: {loading.cbm}" if loading.cbm else "CBM: -",
    )
    pdf.drawString(
        margin,
        route_top - 86,
        f"Packages: {loading.packages}" if loading.packages else "Packages: -",
    )
    if loading.entry_type == "GROUPAGE":
        chargeable_wm = loading.chargeable_wm
        pdf.drawString(
            margin,
            route_top - 100,
            (
                f"Chargeable (W/M): {chargeable_wm:.3f}"
                if chargeable_wm is not None
                else "Chargeable (W/M): -"
            ),
        )
    pdf.drawString(
        margin,
        route_top - 114,
        f"Container Number: {loading.container_number or '-'}",
    )
    pdf.drawString(
        margin,
        route_top - 128,
        "Container Size: "
        + (loading.get_container_size_display() if loading.container_size else "-"),
    )

    notes_top = route_top - 146
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin, notes_top, "Description")
    pdf.setFont("Helvetica", 9)
    text_obj = pdf.beginText(margin, notes_top - 16)
    for line in (loading.item_description or "-").splitlines()[:10]:
        text_obj.textLine(line)
    pdf.drawText(text_obj)

    _draw_international_terms_footer(pdf, margin, 68)
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@login_required
def loading_packing_list_document(request, pk):
    loading = get_object_or_404(Loading.objects.select_related("client"), pk=pk)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 40

    reference = loading.loading_id
    _draw_standard_doc_header(pdf, width, height, "PACKING LIST", reference)

    top = height - 126
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin, top, "Shipment Information")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(margin, top - 16, f"Cargo Reference: {loading.loading_id}")
    pdf.drawString(margin, top - 30, f"Client: {loading.client.name}")
    pdf.drawString(margin, top - 44, f"Entry Type: {loading.get_entry_type_display()}")
    pdf.drawString(
        margin,
        top - 58,
        f"Loading Date: {loading.loading_date.strftime('%Y-%m-%d %H:%M')}",
    )

    if loading.entry_type == "FULL_CONTAINER":
        reference_number = loading.bill_of_lading_number or "-"
        reference_label = "Bill of Lading"
    else:
        reference_number = loading.groupage_note_number or "-"
        reference_label = "Groupage Note"
    pdf.drawString(margin, top - 72, f"{reference_label}: {reference_number}")

    table_top = top - 98
    row_height = 21
    col_widths = [32, 200, 60, 70, 153]
    headers = ["No", "Item Description", "Packages", "Weight (KG)", "CBM / Container"]
    row_data = [
        "1",
        loading.item_description or "-",
        str(loading.packages or "-"),
        f"{loading.weight}" if loading.weight is not None else "-",
        (
            f"{loading.cbm}"
            if loading.cbm is not None
            else (loading.container_number or "-")
        ),
    ]

    x = margin
    pdf.setStrokeColor(colors.HexColor("#CFCFCF"))
    pdf.setFillColor(colors.HexColor("#F8F8F8"))
    for idx, header in enumerate(headers):
        w = col_widths[idx]
        pdf.rect(x, table_top, w, row_height, fill=1, stroke=1)
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(x + 4, table_top + 7, header)
        x += w

    x = margin
    y = table_top - row_height
    for idx, value in enumerate(row_data):
        w = col_widths[idx]
        pdf.setFillColor(colors.white)
        pdf.rect(x, y, w, row_height, fill=1, stroke=1)
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(x + 4, y + 7, str(value)[:45])
        x += w

    route_top = y - 24
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin, route_top, "Route")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(margin, route_top - 16, f"Origin: {loading.origin}")
    pdf.drawString(margin, route_top - 30, f"Destination: {loading.destination}")
    pdf.drawString(
        margin,
        route_top - 44,
        "Container Number: " + (loading.container_number or "-"),
    )
    pdf.drawString(
        margin,
        route_top - 58,
        "Container Size: "
        + (loading.get_container_size_display() if loading.container_size else "-"),
    )

    _draw_international_terms_footer(pdf, margin, 68)
    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    filename = f"logistics_{loading.loading_id}_packing_list.pdf"
    response = HttpResponse(buffer.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@login_required
def loading_update(request, pk):
    if request.user.role == "OFFICE_ADMIN":
        messages.error(request, "You cannot edit loadings")
        return redirect("loading_list")
    loading = get_object_or_404(Loading, pk=pk)
    if loading.is_closed:
        messages.error(request, "This loading is closed and cannot be edited.")
        return redirect("loading_detail", pk=loading.id)
    if request.method == "POST":
        form = LoadingForm(request.POST, instance=loading)
        if form.is_valid():
            form.save()
            messages.success(request, "Loading updated successfully")
            log_audit("loading", "update", loading.id, str(loading), request.user)
            return redirect("loading_detail", pk=loading.id)
    else:
        form = LoadingForm(instance=loading)
    return render(
        request,
        "logistics/loadings/form.html",
        {"form": form, "title": "Update Loading", "loading": loading},
    )


@login_required
def loading_delete(request, pk):
    if not request.user.is_superuser and request.user.role not in {
        "ADMIN",
        "superuser",
        "DIRECTOR",
    }:
        messages.error(request, "Only superusers can delete loadings")
        return redirect("loading_list")
    loading = get_object_or_404(Loading, pk=pk)
    loading_str = str(loading)
    loading_id = loading.id
    loading.delete()
    messages.success(request, "Loading deleted successfully")
    log_audit("loading", "delete", loading_id, loading_str, request.user)
    return redirect("loading_list")


# ===== TRANSIT MANAGEMENT =====


@login_required
def transit_list(request):
    transits = Transit.objects.select_related("loading")
    status = request.GET.get("status", "")
    if status:
        transits = transits.filter(status=status)
    page_obj, query_string, page_range = paginate_queryset(request, transits)
    return render(
        request,
        "logistics/transits/list.html",
        {
            "transits": page_obj,
            "status_filter": status,
            "status_choices": Transit.STATUS_CHOICES,
            "page_obj": page_obj,
            "query_string": query_string,
            "page_range": page_range,
        },
    )


@login_required
def transit_create(request, loading_id=None):
    transit_to_workflow_status = {
        "awaiting": "LOADED",
        "in_transit": "IN_TRANSIT",
        "arrived": "ARRIVED",
    }

    workflow_sequence = [
        "RECEIVED",
        "VERIFIED",
        "ALLOCATED",
        "LOADED",
        "IN_TRANSIT",
        "ARRIVED",
        "DELIVERED",
    ]

    def _move_stepwise_shipment(shipment, target_status, actor):
        current = shipment.status
        if current not in workflow_sequence or target_status not in workflow_sequence:
            return
        current_index = workflow_sequence.index(current)
        target_index = workflow_sequence.index(target_status)
        if target_index <= current_index:
            return
        for next_status in workflow_sequence[current_index + 1 : target_index + 1]:
            transition_shipment(
                shipment=shipment,
                to_status=next_status,
                actor=actor,
                notes=f"Transit synchronization to {next_status}",
            )

    def _move_stepwise_cargo(cargo_item, target_status, actor):
        current = cargo_item.status
        if current not in workflow_sequence or target_status not in workflow_sequence:
            return
        current_index = workflow_sequence.index(current)
        target_index = workflow_sequence.index(target_status)
        if target_index <= current_index:
            return
        for next_status in workflow_sequence[current_index + 1 : target_index + 1]:
            transition_cargo_item(
                cargo_item=cargo_item,
                to_status=next_status,
                actor=actor,
                notes=f"Transit synchronization to {next_status}",
            )

    def _sync_transit_to_workflow(transit, actor):
        shipment = getattr(transit.loading, "workflow_shipment", None)
        if not shipment:
            return
        target_status = transit_to_workflow_status.get(transit.status)
        if not target_status:
            return
        _move_stepwise_shipment(shipment, target_status, actor)
        for cargo_item in shipment.cargo_items.all():
            _move_stepwise_cargo(cargo_item, target_status, actor)

    if request.method == "POST":
        form = TransitForm(request.POST)
        if form.is_valid():
            transit = form.save(commit=False)
            transit.created_by = request.user
            try:
                with transaction.atomic():
                    transit.save()
                    _sync_transit_to_workflow(transit, request.user)
            except WorkflowTransitionError as exc:
                form.add_error(None, str(exc))
                return render(
                    request,
                    "logistics/transits/form.html",
                    {"form": form, "title": "Create Transit"},
                )
            messages.success(request, "Transit created successfully")
            log_audit("transit", "create", transit.id, str(transit), request.user)
            _notify_roles(
                title="Transit started",
                message=f"Loading {transit.loading.loading_id} entered transit ({transit.get_status_display() if hasattr(transit,'get_status_display') else transit.status}).",
                link=f"/transits/{transit.id}/",
                category="logistics",
                roles=["ADMIN", "DIRECTOR", "FINANCE", "OFFICE_ADMIN"],
            )
            return redirect("loading_detail", pk=transit.loading.id)
    else:
        form = TransitForm()
        if loading_id:
            form.fields["loading"].initial = loading_id
    return render(
        request,
        "logistics/transits/form.html",
        {"form": form, "title": "Create Transit"},
    )


@login_required
def transit_update(request, pk):
    if request.user.role == "OFFICE_ADMIN":
        messages.error(request, "You cannot edit transits")
        return redirect("transit_list")
    transit = get_object_or_404(Transit, pk=pk)
    transit_to_workflow_status = {
        "awaiting": "LOADED",
        "in_transit": "IN_TRANSIT",
        "arrived": "ARRIVED",
    }

    workflow_sequence = [
        "RECEIVED",
        "VERIFIED",
        "ALLOCATED",
        "LOADED",
        "IN_TRANSIT",
        "ARRIVED",
        "DELIVERED",
    ]

    def _move_stepwise_shipment(shipment, target_status, actor):
        current = shipment.status
        if current not in workflow_sequence or target_status not in workflow_sequence:
            return
        current_index = workflow_sequence.index(current)
        target_index = workflow_sequence.index(target_status)
        if target_index <= current_index:
            return
        for next_status in workflow_sequence[current_index + 1 : target_index + 1]:
            transition_shipment(
                shipment=shipment,
                to_status=next_status,
                actor=actor,
                notes=f"Transit synchronization to {next_status}",
            )

    def _move_stepwise_cargo(cargo_item, target_status, actor):
        current = cargo_item.status
        if current not in workflow_sequence or target_status not in workflow_sequence:
            return
        current_index = workflow_sequence.index(current)
        target_index = workflow_sequence.index(target_status)
        if target_index <= current_index:
            return
        for next_status in workflow_sequence[current_index + 1 : target_index + 1]:
            transition_cargo_item(
                cargo_item=cargo_item,
                to_status=next_status,
                actor=actor,
                notes=f"Transit synchronization to {next_status}",
            )

    def _sync_transit_to_workflow(updated_transit, actor):
        shipment = getattr(updated_transit.loading, "workflow_shipment", None)
        if not shipment:
            return
        target_status = transit_to_workflow_status.get(updated_transit.status)
        if not target_status:
            return
        _move_stepwise_shipment(shipment, target_status, actor)
        for cargo_item in shipment.cargo_items.all():
            _move_stepwise_cargo(cargo_item, target_status, actor)

    if request.method == "POST":
        form = TransitForm(request.POST, instance=transit)
        if form.is_valid():
            try:
                with transaction.atomic():
                    updated_transit = form.save()
                    _sync_transit_to_workflow(updated_transit, request.user)
            except WorkflowTransitionError as exc:
                form.add_error(None, str(exc))
                return render(
                    request,
                    "logistics/transits/form.html",
                    {"form": form, "title": "Update Transit"},
                )
            messages.success(request, "Transit updated successfully")
            log_audit("transit", "update", transit.id, str(transit), request.user)
            if transit.status == "arrived":
                _notify_roles(
                    title="Cargo arrived",
                    message=f"Loading {transit.loading.loading_id} marked as arrived.",
                    link=f"/transits/{transit.id}/",
                    category="logistics",
                    roles=["ADMIN", "DIRECTOR", "FINANCE", "OFFICE_ADMIN"],
                )
            return redirect("loading_detail", pk=transit.loading.id)
    else:
        form = TransitForm(instance=transit)
    return render(
        request,
        "logistics/transits/form.html",
        {"form": form, "title": "Update Transit"},
    )


# ===== PAYMENT MANAGEMENT =====


@login_required
def payment_list(request):
    lane = _resolve_lane(request)
    payments = _apply_payment_lane(
        Payment.objects.select_related("loading__client"), lane
    )
    filter_type = request.GET.get("filter", "")
    if filter_type == "outstanding":
        payments = payments.filter(balance__gt=0)
    elif filter_type == "paid":
        payments = payments.filter(balance=0)
    page_obj, query_string, page_range = paginate_queryset(request, payments)
    payment_totals_qs = _apply_payment_lane(Payment.objects.all(), lane)
    totals = {
        "total_charged": payment_totals_qs.aggregate(Sum("amount_charged"))[
            "amount_charged__sum"
        ]
        or 0,
        "total_paid": payment_totals_qs.aggregate(Sum("amount_paid"))[
            "amount_paid__sum"
        ]
        or 0,
        "total_outstanding": payment_totals_qs.filter(balance__gt=0).aggregate(
            Sum("balance")
        )["balance__sum"]
        or 0,
    }
    can_view_financial_totals = request.user.role != "OFFICE_ADMIN"
    if not can_view_financial_totals:
        totals = {key: None for key in totals}
    context = {
        "payments": page_obj,
        "filter_type": filter_type,
        **totals,
        "can_view_financial_totals": can_view_financial_totals,
        "page_obj": page_obj,
        "query_string": query_string,
        "page_range": page_range,
        "active_lane": lane,
        "active_lane_label": _lane_label(lane),
        "can_switch_lane": _can_switch_lane(request.user),
    }
    return render(request, "logistics/payments/list.html", context)


@finance_required
@login_required
def payment_create(request, loading_id=None):
    if request.user.role == "OFFICE_ADMIN":
        messages.error(request, "You cannot create payments")
        return redirect("payment_list")

    target_invoice = None
    if loading_id:
        loading = get_object_or_404(Loading, pk=loading_id)
        target_invoice = (
            FinalInvoice.objects.filter(transaction__customer=loading.client)
            .order_by("-is_confirmed", "-created_at")
            .first()
        )

    messages.info(
        request,
        "Freight payments are now recorded directly from the final invoice. Use the invoice Record Payment action to generate receipts.",
    )
    if target_invoice:
        return redirect(
            _final_invoice_route_name(target_invoice, "detail"), pk=target_invoice.pk
        )
    return redirect(f"{reverse('final_invoice_list')}?lane=logistics")


@login_required
def dashboard(request):
    """Serve a branded landing page for guests and the KPI dashboard for staff."""
    landing_preview = (request.GET.get("landing_preview") or "").strip() == "1"
    user_role = getattr(request.user, "role", None)
    can_view_financials = request.user.is_authenticated and (
        request.user.is_superuser
        or user_role
        in {
            "ADMIN",
            "DIRECTOR",
            "FINANCE",
        }
    )
    active_lane = _resolve_lane(request) if request.user.is_authenticated else "all"
    scoped_clients = Client.objects.all()
    scoped_loadings = _apply_loading_lane(Loading.objects.all(), active_lane)
    scoped_transits = _apply_loading_lane(Transit.objects.all(), active_lane)
    scoped_transactions = _apply_transaction_lane(
        Transaction.objects.all(), active_lane
    )
    context = {
        "active_lane": active_lane,
        "active_lane_label": _lane_label(active_lane),
        "can_switch_lane": request.user.is_authenticated
        and (
            request.user.is_superuser or user_role in {"ADMIN", "DIRECTOR", "FINANCE"}
        ),
        # Logistics
        "total_clients": scoped_clients.count(),
        "total_loadings": scoped_loadings.count(),
        "total_transits": scoped_transits.count(),
        "pending_containers": _apply_loading_lane(
            ContainerReturn.objects.filter(status="pending"), active_lane
        ).count(),
        "pending_verifications": _apply_payment_lane(
            PaymentTransaction.objects.filter(verification_status="pending"),
            active_lane,
        ).count(),
        # Sourcing / Trade
        "total_transactions": scoped_transactions.count(),
        "active_transactions": scoped_transactions.exclude(
            status__in=["PAID", "SHIPPED", "DELIVERED"]
        ).count(),
        "recent_transactions": scoped_transactions.select_related("customer")[:5],
        # Shared recent data
        "recent_clients": scoped_clients[:5],
        "recent_loadings": scoped_loadings[:5],
        "can_view_financials": can_view_financials,
    }
    if request.user.is_authenticated and can_view_financials:
        context.update(
            {
                "total_revenue": DirectorReportingService.total_revenue(),
                "outstanding_balance": DirectorReportingService.outstanding_balances(),
                "active_shipments": DirectorReportingService.active_shipments_count(),
                "conversion": DirectorReportingService.conversion_rate(),
                "top_clients": DirectorReportingService.top_clients(5),
                "profit_estimate": DirectorReportingService.profit_estimate(),
                "pending_payments_freight": Payment.objects.filter(
                    balance__gt=0
                ).count(),
            }
        )
    if not request.user.is_authenticated or landing_preview:
        return render(request, "logistics/landing.html", context)
    return render(request, "logistics/dashboard.html", context)


@finance_required
@login_required
def payment_update(request, pk):
    payment = get_object_or_404(
        Payment.objects.select_related("loading__client"), pk=pk
    )
    messages.error(
        request,
        "Payments are locked after creation. Record client payments from the final invoice instead of editing this record.",
    )
    return redirect("payment_detail", pk=payment.pk)


@finance_required
@login_required
def payment_detail(request, pk):
    payment = get_object_or_404(
        Payment.objects.select_related("loading__client"), pk=pk
    )
    transactions = payment.transactions.select_related(
        "created_by", "verified_by"
    ).all()
    if request.method == "POST":
        action = request.POST.get("action", "create_transaction")
        if action == "verify_transaction":
            if not request.user.is_superuser and request.user.role not in {
                "ADMIN",
                "superuser",
            }:
                messages.error(request, "Only superusers can verify payments.")
                return redirect("payment_detail", pk=pk)
            transaction = get_object_or_404(
                payment.transactions.select_related("payment"),
                pk=request.POST.get("transaction_id"),
            )
            new_status = request.POST.get("verification_status", "pending")
            valid_statuses = {
                choice for choice, _ in PaymentTransaction.VERIFICATION_CHOICES
            }
            if new_status not in valid_statuses:
                messages.error(request, "Invalid verification status selected.")
                return redirect("payment_detail", pk=pk)
            notes = request.POST.get("verification_notes", "").strip()
            transaction.verification_status = new_status
            transaction.verification_notes = notes
            if new_status == "pending":
                transaction.verified_by = None
                transaction.verified_at = None
            else:
                transaction.verified_by = request.user
                transaction.verified_at = timezone.now()
            transaction.save()
            messages.success(
                request,
                f"Marked transaction {transaction.receipt_number} as {transaction.get_verification_status_display().lower()}.",
            )
            return redirect("payment_detail", pk=pk)
        else:
            messages.error(
                request,
                "Direct payment entry is disabled. Open the linked final invoice and record payment there to generate receipts.",
            )
            if payment.final_invoice_id:
                return redirect(
                    _final_invoice_route_name(payment.final_invoice, "detail"),
                    pk=payment.final_invoice_id,
                )
            return redirect(f"{reverse('final_invoice_list')}?lane=logistics")
    else:
        form = PaymentTransactionForm(
            initial={
                "payment_method": payment.payment_method or "cash",
                "payment_date": timezone.now(),
            }
        )
    context = {
        "payment": payment,
        "transactions": transactions,
        "transaction_form": form,
        "verification_choices": PaymentTransaction.VERIFICATION_CHOICES,
        "can_verify": request.user.role in {"ADMIN", "superuser"},
    }
    return render(request, "logistics/payments/detail.html", context)


@finance_required
@login_required
def payment_invoice(request, pk):
    payment = get_object_or_404(
        Payment.objects.select_related("loading__client"), pk=pk
    )
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 40
    primary = colors.HexColor("#1E1A23")
    accent = colors.HexColor("#F4C21F")

    _draw_standard_doc_header(
        pdf, width, height, "FREIGHT INVOICE", payment.invoice_number
    )

    pdf.setFillColor(colors.black)
    info_top = height - 115
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin, info_top, "Invoice Details")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(
        margin, info_top - 18, f"Issue Date: {timezone.now().strftime('%Y-%m-%d')}"
    )
    pdf.drawString(margin, info_top - 34, f"Prepared By: {payment.created_by.username}")
    pdf.drawString(margin, info_top - 50, f"Loading ID: {payment.loading.loading_id}")
    invoice_ref = f"FI-{payment.final_invoice_id}" if payment.final_invoice_id else "-"
    pdf.drawString(margin, info_top - 66, f"Attached Invoice: {invoice_ref}")

    bill_top = info_top - 96
    box_width = (width / 2) - margin
    pdf.roundRect(margin, bill_top - 110, box_width - 10, 110, 8, stroke=1)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin + 10, bill_top - 15, "Bill To:")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(margin + 10, bill_top - 32, payment.loading.client.name)
    pdf.drawString(
        margin + 10, bill_top - 48, f"Client ID: {payment.loading.client.client_id}"
    )
    pdf.drawString(
        margin + 10, bill_top - 64, f"Contact: {payment.loading.client.phone}"
    )
    pdf.drawString(margin + 10, bill_top - 80, payment.loading.client.address[:60])

    ship_left = margin + box_width + 5
    pdf.roundRect(ship_left, bill_top - 110, box_width - 10, 110, 8, stroke=1)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(ship_left + 10, bill_top - 15, "Shipment")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(
        ship_left + 10,
        bill_top - 32,
        f"Route: {payment.loading.origin} -> {payment.loading.destination}",
    )
    pdf.drawString(
        ship_left + 10,
        bill_top - 48,
        f"Container: {payment.loading.container_number}",
    )
    container_size_label = (
        payment.loading.get_container_size_display()
        if payment.loading.container_size
        else "N/A"
    )
    pdf.drawString(
        ship_left + 10,
        bill_top - 64,
        f"Container Size: {container_size_label}",
    )
    weight_label = f"{payment.loading.weight} KG" if payment.loading.weight else "N/A"
    pdf.drawString(
        ship_left + 10,
        bill_top - 80,
        f"Weight: {weight_label}",
    )
    if payment.loading.entry_type == "GROUPAGE":
        cbm_label = payment.loading.cbm if payment.loading.cbm is not None else "N/A"
        basis_label = payment.get_billing_basis_display()
        rate_label = (
            f"${payment.billing_rate:,.2f}"
            if payment.billing_rate is not None
            else "N/A"
        )
        pdf.drawString(ship_left + 10, bill_top - 96, f"CBM: {cbm_label}")
        pdf.drawString(ship_left + 10, bill_top - 112, f"Billing Basis: {basis_label}")
        pdf.drawString(ship_left + 10, bill_top - 128, f"Billing Rate: {rate_label}")
        loading_date_y = bill_top - 144
    else:
        loading_date_y = bill_top - 96
    pdf.drawString(
        ship_left + 10,
        loading_date_y,
        f"Loading Date: {payment.loading.loading_date.strftime('%Y-%m-%d')}",
    )

    summary_top = (
        bill_top - 170 if payment.loading.entry_type == "GROUPAGE" else bill_top - 120
    )
    pdf.setFillColor(accent)
    pdf.rect(margin, summary_top - 80, width - (2 * margin), 80, fill=1, stroke=0)
    pdf.setFillColor(primary)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin + 15, summary_top - 25, "Amount Due")
    pdf.drawString(margin + 190, summary_top - 25, "Amount Paid")
    pdf.drawString(margin + 365, summary_top - 25, "Balance")
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(margin + 15, summary_top - 55, f"${payment.amount_charged:,.2f}")
    pdf.drawString(margin + 190, summary_top - 55, f"${payment.amount_paid:,.2f}")
    pdf.drawString(margin + 365, summary_top - 55, f"${payment.balance:,.2f}")

    pdf.setFillColor(colors.black)
    notes_top = summary_top - 110
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin, notes_top, "Notes")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        margin,
        notes_top - 16,
        "1. Invoice valid for 7 days from date of issue.",
    )
    pdf.drawString(
        margin,
        notes_top - 30,
        "2. Partial payments are recorded; outstanding balance must be cleared before release.",
    )
    pdf.drawString(
        margin,
        notes_top - 44,
        "3. Thank you for choosing GMI TERRALINK Logistics Portal.",
    )

    _draw_international_terms_footer(pdf, margin, 60)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="invoice_{payment.invoice_number}.pdf"'
    )
    return response


@finance_required
@login_required
def payment_receipt(request, transaction_id):
    transaction = get_object_or_404(
        PaymentTransaction.objects.select_related(
            "payment__loading__client", "created_by", "verified_by"
        ),
        pk=transaction_id,
    )
    payment = transaction.payment
    if transaction.verification_status != "approved":
        messages.error(request, "This payment has not been verified yet.")
        return redirect("payment_detail", pk=payment.pk)
    paid_up_to = (
        payment.transactions.filter(pk__lte=transaction.pk).aggregate(
            total=Sum("amount")
        )["total"]
        or transaction.amount
    )
    balance_after = payment.amount_charged - paid_up_to

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 40
    _draw_standard_doc_header(
        pdf, width, height, "FREIGHT PAYMENT RECEIPT", transaction.receipt_number
    )

    pdf.setFillColor(colors.black)
    info_top = height - 105
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin, info_top, "Received From")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(margin, info_top - 18, payment.loading.client.name)
    pdf.drawString(margin, info_top - 34, f"Invoice: {payment.invoice_number}")
    pdf.drawString(
        margin,
        info_top - 50,
        f"Route: {payment.loading.origin} -> {payment.loading.destination}",
    )

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin, info_top - 80, "Amount Details")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(margin, info_top - 100, f"Amount Paid: ${transaction.amount:,.2f}")
    pdf.drawString(
        margin,
        info_top - 118,
        f"Payment Date: {transaction.payment_date.strftime('%Y-%m-%d')}",
    )
    pdf.drawString(
        margin, info_top - 136, f"Method: {transaction.get_payment_method_display()}"
    )
    if transaction.reference:
        pdf.drawString(margin, info_top - 154, f"Reference: {transaction.reference}")
    pdf.drawString(
        margin,
        info_top - 172,
        f"Outstanding After Payment: ${balance_after:,.2f}",
    )

    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        margin,
        info_top - 210,
        f"Recorded By: {transaction.created_by.username} on {transaction.created_at.strftime('%Y-%m-%d %H:%M')}",
    )
    _draw_international_terms_footer(pdf, margin, 60)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="receipt_{transaction.receipt_number}.pdf"'
    )
    return response


# ===== CONTAINER RETURNS =====


@login_required
def container_return_list(request):
    containers = ContainerReturn.objects.select_related("loading")
    status = request.GET.get("status", "")
    if status:
        containers = containers.filter(status=status)
    page_obj, query_string, page_range = paginate_queryset(request, containers)
    return render(
        request,
        "logistics/containers/list.html",
        {
            "containers": page_obj,
            "status_filter": status,
            "status_choices": ContainerReturn.STATUS_CHOICES,
            "page_obj": page_obj,
            "query_string": query_string,
            "page_range": page_range,
        },
    )


@login_required
def container_return_create(request):
    if request.method == "POST":
        form = ContainerReturnForm(request.POST)
        if form.is_valid():
            container = form.save(commit=False)
            container.created_by = request.user
            container.save()
            messages.success(request, "Container return recorded")
            log_audit(
                "container_return", "create", container.id, str(container), request.user
            )
            _notify_roles(
                title="Container return recorded",
                message=f"Container {container.container_number or container.id} return logged.",
                link="/containers/",
                category="logistics",
                roles=["ADMIN", "DIRECTOR", "FINANCE", "OFFICE_ADMIN"],
            )
            return redirect("container_return_list")
    else:
        form = ContainerReturnForm()
    return render(
        request,
        "logistics/containers/form.html",
        {"form": form, "title": "Record Container Return"},
    )


@login_required
def container_return_update(request, pk):
    if request.user.role == "OFFICE_ADMIN":
        messages.error(request, "You cannot edit container returns")
        return redirect("container_return_list")
    container = get_object_or_404(ContainerReturn, pk=pk)
    if request.method == "POST":
        form = ContainerReturnForm(request.POST, instance=container)
        if form.is_valid():
            form.save()
            messages.success(request, "Container return updated successfully")
            log_audit(
                "container_return", "update", container.id, str(container), request.user
            )
            return redirect("container_return_list")
    else:
        form = ContainerReturnForm(instance=container)
    return render(
        request,
        "logistics/containers/form.html",
        {"form": form, "title": "Update Container Return"},
    )


# ===== TRANSACTION MANAGEMENT =====


@login_required
def transaction_list(request):
    lane = _resolve_lane(request)
    transactions = _apply_transaction_lane(
        Transaction.objects.select_related("customer", "created_by").annotate(
            sourcing_entry_count=Count("sourcing_entries", distinct=True)
        ),
        lane,
    )
    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "").strip()
    if search:
        transactions = transactions.filter(
            Q(transaction_id__icontains=search)
            | Q(customer__name__icontains=search)
            | Q(customer__client_id__icontains=search)
        )
    if status:
        transactions = transactions.filter(status=status)
    page_obj, query_string, page_range = paginate_queryset(request, transactions)
    for transaction in page_obj:
        _apply_transaction_status_badge(
            transaction, sourcing_entry_count=transaction.sourcing_entry_count
        )
    return render(
        request,
        "logistics/transactions/list.html",
        {
            "transactions": page_obj,
            "search": search,
            "status_filter": status,
            "status_choices": Transaction.STATUS_CHOICES,
            "page_obj": page_obj,
            "query_string": query_string,
            "page_range": page_range,
            "active_lane": lane,
            "active_lane_label": _lane_label(lane),
            "can_switch_lane": _can_switch_lane(request.user),
        },
    )


@login_required
def transaction_create(request):
    if request.method == "POST":
        form = TransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.created_by = request.user
            transaction.save()
            messages.success(
                request, f"Transaction {transaction.transaction_id} created"
            )
            _notify_roles(
                title="New trade transaction",
                message=f"Transaction {transaction.transaction_id} opened for {transaction.customer.name}.",
                link=f"/transactions/{transaction.pk}/",
                category="trading",
                roles=["ADMIN", "DIRECTOR", "FINANCE", "PROCUREMENT"],
            )
            return redirect("transaction_detail", pk=transaction.pk)
    else:
        form = TransactionForm()
    return render(
        request,
        "logistics/transactions/form.html",
        {"form": form, "title": "Create Transaction", "transaction": None},
    )


@login_required
def transaction_detail(request, pk):
    transaction = get_object_or_404(
        Transaction.objects.select_related("customer", "created_by"), pk=pk
    )
    sourcing_entry_count = transaction.sourcing_entries.count()
    _apply_transaction_status_badge(
        transaction, sourcing_entry_count=sourcing_entry_count
    )
    fulfillment_order = (
        FulfillmentOrder.objects.select_related(
            "transaction", "created_by", "final_invoice"
        )
        .filter(transaction=transaction)
        .first()
    )
    documents = transaction.documents.select_related("uploaded_by").order_by(
        "-timestamp"
    )
    pi_documents = documents.filter(document_type="CLIENT_PI")
    latest_invoice = transaction.final_invoices.order_by("-created_at").first()
    total_paid = (
        transaction.payment_records.aggregate(total=Sum("amount"))["total"] or 0
    )
    invoice_balance = 0
    shipping_charge_included = False
    if latest_invoice:
        invoice_balance = max(latest_invoice.total_amount - total_paid, 0)
        shipping_charge_included = (
            (latest_invoice.sourcing_fee or 0)
            + (latest_invoice.shipping_cost or 0)
            + (latest_invoice.service_fee or 0)
        ) > 0
    final_invoices = list(transaction.final_invoices.select_related("created_by")[:10])
    for fi in final_invoices:
        paid_total = fi.payment_records.aggregate(total=Sum("amount"))["total"] or 0
        if paid_total <= 0:
            paid_total = (
                fi.transaction.payment_records.aggregate(total=Sum("amount"))["total"]
                or 0
            )
        fi.can_edit_invoice = paid_total <= 0
    fulfillment_lines = []
    shipment_legs = []
    if fulfillment_order:
        fulfillment_lines = fulfillment_order.lines.select_related(
            "inventory_item", "inventory_item__supplier"
        )
        shipment_legs = fulfillment_order.legs.all()
    fulfillment_receipt_numbers_display = "No Receipt"
    if fulfillment_order:
        payment_qs = transaction.payment_records.select_related("receipt")
        scoped_payments = []
        if fulfillment_order.final_invoice_id:
            scoped_payments = list(
                payment_qs.filter(final_invoice=fulfillment_order.final_invoice)
            )
        payments = scoped_payments or list(payment_qs)
        receipt_numbers = sorted(
            {
                payment.receipt.receipt_number
                for payment in payments
                if getattr(payment, "receipt", None) and payment.receipt.receipt_number
            }
        )
        if receipt_numbers:
            fulfillment_receipt_numbers_display = ", ".join(receipt_numbers)
    final_invoice_purchase_orders = []
    if fulfillment_order and fulfillment_order.final_invoice_id:
        final_invoice_purchase_orders = (
            fulfillment_order.final_invoice.purchase_orders.select_related("created_by")
        )
    context = {
        "transaction": transaction,
        "documents": documents[:20],
        "document_archives": transaction.document_archives.select_related(
            "archived_by", "document"
        )[:20],
        "pi_documents": pi_documents,
        "doc_form": DocumentForm(),
        "proformas": transaction.proforma_invoices.select_related("created_by")[:10],
        "final_invoices": final_invoices,
        "latest_invoice": latest_invoice,
        "trade_total_paid": total_paid,
        "trade_balance": invoice_balance,
        "shipping_charge_included": shipping_charge_included,
        "purchase_orders": transaction.purchase_orders.select_related("created_by")[:5],
        "trade_payments": transaction.payment_records.select_related("created_by")[:10],
        "fulfillment_order": fulfillment_order,
        "fulfillment_receipt_numbers_display": fulfillment_receipt_numbers_display,
        "fulfillment_lines": fulfillment_lines,
        "shipment_legs": shipment_legs,
        "final_invoice_purchase_orders": final_invoice_purchase_orders,
        "transaction_inventory_items": transaction.inventory_items.select_related(
            "supplier"
        ),
        "sourcing_entry_count": sourcing_entry_count,
    }
    closure_items, closure_ready = evaluate_transaction_closure(transaction)
    context["closure_items"] = closure_items
    context["closure_ready"] = closure_ready
    return render(request, "logistics/transactions/detail.html", context)


@login_required
def document_archive_list(request):
    archives = DocumentArchive.objects.select_related(
        "transaction__customer", "document", "archived_by"
    ).order_by("-created_at")
    page_obj, query_string, page_range = paginate_queryset(request, archives)
    return render(
        request,
        "logistics/documents/archive_list.html",
        {
            "archives": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "page_range": page_range,
        },
    )


@login_required
def transaction_update(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk)
    if transaction.is_closed:
        messages.error(request, "This transaction is closed and cannot be edited.")
        return redirect("transaction_detail", pk=transaction.pk)
    if request.method == "POST":
        form = TransactionForm(request.POST, instance=transaction)
        if form.is_valid():
            form.save()
            messages.success(request, "Transaction updated")
            return redirect("transaction_detail", pk=transaction.pk)
    else:
        form = TransactionForm(instance=transaction)
    return render(
        request,
        "logistics/transactions/form.html",
        {"form": form, "title": "Update Transaction", "transaction": transaction},
    )


@login_required
@login_required
def transaction_document_upload(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk)
    if request.method != "POST":
        return redirect("transaction_detail", pk=pk)
    form = DocumentForm(request.POST, request.FILES)
    if form.is_valid():
        document = form.save(commit=False)
        document.transaction = transaction
        document.uploaded_by = request.user
        # Extract text from the uploaded file
        uploaded_file = request.FILES.get("original_file")
        if uploaded_file:
            document.extracted_text = _extract_text_from_file(uploaded_file)
        # If this is a Client PI, run the structured parser too
        if (
            form.cleaned_data.get("document_type") == "CLIENT_PI"
            and document.extracted_text
        ):
            document.structured_data = parse_purchase_inquiry(document.extracted_text)
        document.save()
        if document.extracted_text or document.structured_data:
            DocumentArchive.create_from_document(document, archived_by=request.user)
        if document.document_type == "CLIENT_PI":
            _notify_roles(
                title="Client PI uploaded",
                message=(
                    f"A client PI document was uploaded for transaction "
                    f"{transaction.transaction_id}. Review the extracted PI to open a proforma invoice or generate a sourcing document."
                ),
                link=reverse("transaction_detail", kwargs={"pk": transaction.pk}),
                category="document",
            )
            messages.success(
                request,
                "Client PI uploaded and text extracted. Review the extracted PI below, then choose either Proforma Invoice or Generate Sourcing Document.",
            )
        else:
            _notify_roles(
                title="Document uploaded",
                message=(
                    f"A {document.get_document_type_display()} document was uploaded "
                    f"for transaction {transaction.transaction_id}."
                ),
                link=reverse("transaction_detail", kwargs={"pk": transaction.pk}),
                category="document",
            )
            messages.success(request, "Document uploaded successfully.")
    else:
        messages.error(request, "Please provide a valid document upload")
    return redirect("transaction_detail", pk=pk)


@login_required
def document_edit_pi(request, pk):
    """Allow editing the structured PI data extracted from a CLIENT_PI document."""
    document = get_object_or_404(Document, pk=pk, document_type="CLIENT_PI")
    if request.method == "POST":
        sd = document.structured_data or {}
        sd["client_name"] = request.POST.get("client_name", "").strip()
        sd["contact_person"] = request.POST.get("contact_person", "").strip()
        sd["phone"] = request.POST.get("phone", "").strip()
        sd["email"] = request.POST.get("email", "").strip()
        sd["address"] = request.POST.get("address", "").strip()
        sd["subject"] = request.POST.get("subject", "").strip()
        sd["deadline"] = request.POST.get("deadline", "").strip()
        # Items: one item name per line
        items_text = request.POST.get("items_text", "")
        sd["items"] = [
            {"name": line.strip()} for line in items_text.splitlines() if line.strip()
        ]
        document.structured_data = sd
        document.save(update_fields=["structured_data"])
        next_step = (request.POST.get("next_step") or "").strip()
        if next_step == "sourcing":
            existing_sourcing, _ = _ensure_sourcing_entry_for_transaction(
                document.transaction,
                preferred_user=request.user,
                pi_document=document,
            )
            if document.transaction.status == "RECEIVED":
                Transaction.objects.filter(pk=document.transaction.pk).update(
                    status="SENT_TO_SOURCING"
                )
            _notify_roles(
                title="Sourcing document generated",
                message=(
                    f"A sourcing document was generated for transaction "
                    f"{document.transaction.transaction_id}."
                ),
                link=reverse(
                    "transaction_detail", kwargs={"pk": document.transaction.pk}
                ),
                category="document",
            )
            messages.success(
                request,
                "PI data updated. Sourcing document generated and ready for printing or quotation capture.",
            )
            if existing_sourcing:
                return redirect("sourcing_update", pk=existing_sourcing.pk)
            return redirect(f"{reverse('sourcing_create')}?from_doc={document.pk}")
        if next_step == "proforma":
            messages.success(request, "PI data updated. Opening proforma form.")
            return redirect(f"{reverse('proforma_create')}?from_doc={document.pk}")

        messages.success(request, "PI data updated.")
        return redirect("transaction_detail", pk=document.transaction.pk)
    # GET — not used (form is inline on transaction_detail), redirect back
    return redirect("transaction_detail", pk=document.transaction.pk)


def _build_sourcing_initial_from_document(pi_document):
    """Build sourcing form initial values from an extracted PI document."""
    sd = pi_document.structured_data or {}
    initial = {
        "transaction": pi_document.transaction,
        "item_details": items_to_sourcing_lines(sd),
        "notes": build_sourcing_notes(sd) if sd else "",
    }
    return initial


def _prefill_proforma_items_from_sourcing(sourcing):
    """Convert sourcing findings into prefilled proforma line items."""
    prefill_items = []
    prices = sourcing.unit_prices or {}
    for item in sourcing.item_details or []:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or item.get("description") or "").strip()
        if not name:
            continue
        quantity = item.get("quantity") or "1"
        unit_price = prices.get(name, "") if isinstance(prices, dict) else ""
        prefill_items.append(
            {
                "description": name,
                "quantity": str(quantity),
                "unit_price": unit_price,
                "sales_price": unit_price,
            }
        )
    return prefill_items


def _parse_quote_fees(
    post_data, *, shipping_key="shipping_fee", handling_key="handling_fee"
):
    """Parse common quote fee fields from a POST payload."""
    from decimal import Decimal, InvalidOperation

    errors = []
    fee_values = {}
    labels = {
        "sourcing_fee": "Sourcing fee",
        handling_key: "Handling fee",
        shipping_key: "Shipping fee",
    }

    for field_name, label in labels.items():
        raw_value = (post_data.get(field_name) or "0").strip()
        try:
            fee_value = Decimal(raw_value or "0")
        except InvalidOperation:
            errors.append(f"{label} must be a valid non-negative number.")
            fee_value = Decimal("0")
        if fee_value < 0:
            errors.append(f"{label} must be a valid non-negative number.")
            fee_value = Decimal("0")
        fee_values[field_name] = fee_value

    return fee_values, errors


def _build_proforma_form_values(*, post_data=None, proforma=None):
    if post_data is not None:
        return {
            "sourcing_fee": post_data.get("sourcing_fee", "0"),
            "handling_fee": post_data.get("handling_fee", "0"),
            "shipping_fee": post_data.get("shipping_fee", "0"),
            "notes": post_data.get("notes", ""),
        }
    if proforma is not None:
        return {
            "sourcing_fee": proforma.sourcing_fee,
            "handling_fee": proforma.handling_fee,
            "shipping_fee": proforma.shipping_fee,
            "notes": "",
        }
    return {
        "sourcing_fee": "0",
        "handling_fee": "0",
        "shipping_fee": "0",
        "notes": "",
    }


# ===== SOURCING MODULE =====


@login_required
@procurement_required
def sourcing_list(request):
    lane = _resolve_lane(request)
    sourcing_records = _apply_sourcing_lane(
        Sourcing.objects.select_related("transaction", "created_by"), lane
    )
    page_obj, query_string, page_range = paginate_queryset(request, sourcing_records)
    return render(
        request,
        "logistics/sourcing/list.html",
        {
            "records": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "page_range": page_range,
            "active_lane": lane,
            "active_lane_label": _lane_label(lane),
            "can_switch_lane": _can_switch_lane(request.user),
        },
    )


@login_required
@procurement_required
def inventory_list(request):
    lane = _resolve_lane(request)
    items = _apply_inventory_lane(
        InventoryItem.objects.select_related(
            "supplier", "updated_by", "transaction__customer"
        ).prefetch_related("fulfillment_lines"),
        lane,
    )
    page_obj, query_string, page_range = paginate_queryset(request, items)
    return render(
        request,
        "logistics/inventory/list.html",
        {
            "items": page_obj,
            "supplier_form": SupplierForm(),
            "page_obj": page_obj,
            "query_string": query_string,
            "page_range": page_range,
            "active_lane": lane,
            "active_lane_label": _lane_label(lane),
            "can_switch_lane": _can_switch_lane(request.user),
        },
    )


@login_required
@procurement_required
def inventory_create(request):
    if request.method == "POST":
        form = InventoryItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.updated_by = request.user
            item.save()
            messages.success(request, "Warehouse item created")
            return redirect("inventory_list")
    else:
        form = InventoryItemForm()
    return render(
        request,
        "logistics/inventory/form.html",
        {"form": form, "title": "Add Warehouse Item"},
    )


@login_required
@procurement_required
def inventory_update(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    if request.method == "POST":
        form = InventoryItemForm(request.POST, instance=item)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.updated_by = request.user
            updated.save()
            messages.success(request, "Warehouse item updated")
            return redirect("inventory_list")
    else:
        form = InventoryItemForm(instance=item)
    return render(
        request,
        "logistics/inventory/form.html",
        {"form": form, "title": "Update Warehouse Item", "item": item},
    )


@login_required
@procurement_required
def fulfillment_order_create(request, transaction_pk):
    transaction = get_object_or_404(
        Transaction.objects.select_related("customer"), pk=transaction_pk
    )
    existing_order = FulfillmentOrder.objects.filter(transaction=transaction).first()
    if existing_order:
        return redirect("fulfillment_order_update", pk=existing_order.pk)

    initial = {}
    final_invoice_id = (request.GET.get("final_invoice") or "").strip()
    if final_invoice_id:
        linked_invoice = get_object_or_404(
            FinalInvoice.objects.select_related("transaction"),
            pk=final_invoice_id,
            transaction=transaction,
        )
        linked_invoice_total_paid = (
            linked_invoice.payment_records.aggregate(total=Sum("amount"))["total"] or 0
        )
        if linked_invoice_total_paid <= 0:
            linked_invoice_total_paid = (
                linked_invoice.transaction.payment_records.aggregate(
                    total=Sum("amount")
                )["total"]
                or 0
            )
        if linked_invoice_total_paid < (linked_invoice.total_amount or 0):
            messages.error(
                request,
                "Fulfillment can only start from a fully paid final invoice.",
            )
            return redirect(
                _final_invoice_route_name(linked_invoice, "detail"),
                pk=linked_invoice.pk,
            )
        initial = {
            "final_invoice": linked_invoice,
        }

    form_instance = FulfillmentOrder(transaction=transaction)

    if request.method == "POST":
        post_data = request.POST.copy()
        if not post_data.get("final_invoice") and final_invoice_id:
            post_data["final_invoice"] = final_invoice_id
        form = FulfillmentOrderForm(
            post_data, transaction=transaction, instance=form_instance
        )
        if form.is_valid():
            order = form.save(commit=False)
            order.transaction = transaction
            order.created_by = request.user
            order.save()
            messages.success(request, "Fulfillment workflow created.")
            _notify_roles(
                title="Fulfillment started",
                message=f"Fulfillment workflow opened for {transaction.transaction_id}.",
                link=f"/transactions/{transaction.pk}/",
                category="trading",
                roles=["ADMIN", "DIRECTOR", "FINANCE", "PROCUREMENT"],
            )
            return redirect("transaction_detail", pk=transaction.pk)
        messages.error(
            request,
            "Fulfillment workflow was not saved. Please review the highlighted fields.",
        )
    else:
        form = FulfillmentOrderForm(
            transaction=transaction,
            initial=initial,
            instance=form_instance,
        )
    return render(
        request,
        "logistics/fulfillment/order_form.html",
        {
            "form": form,
            "title": "Create Fulfillment Workflow",
            "transaction": transaction,
        },
    )


@login_required
@role_required("PROCUREMENT", "DIRECTOR", "FINANCE", "ADMIN")
def fulfillment_list(request):
    lane = _resolve_lane(request)
    orders = _apply_fulfillment_lane(
        FulfillmentOrder.objects.select_related(
            "transaction__customer", "created_by", "final_invoice"
        ).prefetch_related(
            "lines",
            "legs",
            "final_invoice__payment_records__receipt",
            "transaction__payment_records__receipt",
        ),
        lane,
    )
    status = (request.GET.get("status") or "").strip()
    invoice_filter = (request.GET.get("invoice") or "").strip()
    if status:
        orders = orders.filter(status=status)
    if invoice_filter.isdigit():
        orders = orders.filter(final_invoice_id=invoice_filter)
    page_obj, query_string, page_range = paginate_queryset(request, orders)
    for order in page_obj:
        scoped_payments = []
        if order.final_invoice_id:
            scoped_payments = list(order.final_invoice.payment_records.all())
        payments = scoped_payments or list(order.transaction.payment_records.all())
        receipt_numbers = sorted(
            {
                payment.receipt.receipt_number
                for payment in payments
                if getattr(payment, "receipt", None) and payment.receipt.receipt_number
            }
        )
        order.receipt_numbers_display = (
            ", ".join(receipt_numbers) if receipt_numbers else "No Receipt"
        )
    return render(
        request,
        "logistics/fulfillment/list.html",
        {
            "orders": page_obj,
            "status": status,
            "status_choices": FulfillmentOrder.STATUS_CHOICES,
            "invoice_filter": invoice_filter,
            "page_obj": page_obj,
            "query_string": query_string,
            "page_range": page_range,
            "active_lane": lane,
            "active_lane_label": _lane_label(lane),
            "can_switch_lane": _can_switch_lane(request.user),
        },
    )


@login_required
@procurement_required
def fulfillment_order_update(request, pk):
    order = get_object_or_404(
        FulfillmentOrder.objects.select_related("transaction__customer"), pk=pk
    )
    if order.transaction.is_closed:
        messages.error(
            request, "This transaction is closed; fulfillment cannot be edited."
        )
        return redirect("transaction_detail", pk=order.transaction.pk)
    if request.method == "POST":
        form = FulfillmentOrderForm(
            request.POST, instance=order, transaction=order.transaction
        )
        if form.is_valid():
            previous_status = order.status
            form.save()
            messages.success(request, "Fulfillment workflow updated.")
            new_status = order.status
            if new_status != previous_status and new_status in {
                "IN_TRANSIT",
                "DISPATCHED",
                "DELIVERED",
            }:
                _notify_roles(
                    title=f"Fulfillment {order.get_status_display() if hasattr(order,'get_status_display') else new_status}",
                    message=f"{order.transaction.transaction_id} fulfillment is now {new_status}.",
                    link=f"/transactions/{order.transaction.pk}/",
                    category="trading",
                    roles=["ADMIN", "DIRECTOR", "FINANCE", "PROCUREMENT"],
                )
            return redirect("transaction_detail", pk=order.transaction.pk)
    else:
        form = FulfillmentOrderForm(instance=order, transaction=order.transaction)
    return render(
        request,
        "logistics/fulfillment/order_form.html",
        {
            "form": form,
            "title": "Update Fulfillment Workflow",
            "transaction": order.transaction,
            "order": order,
        },
    )


@login_required
@procurement_required
def fulfillment_line_create(request, order_pk):
    order = get_object_or_404(
        FulfillmentOrder.objects.select_related("transaction__customer"), pk=order_pk
    )
    if request.method == "POST":
        form = FulfillmentLineForm(request.POST, order=order)
        if form.is_valid():
            line = form.save(commit=False)
            line.order = order
            line.save()
            messages.success(request, "Warehouse stock allocated to fulfillment.")
            return redirect("transaction_detail", pk=order.transaction.pk)
    else:
        form = FulfillmentLineForm(order=order)
    return render(
        request,
        "logistics/fulfillment/line_form.html",
        {
            "form": form,
            "title": "Allocate Warehouse Stock",
            "order": order,
            "transaction": order.transaction,
        },
    )


@login_required
@procurement_required
def fulfillment_line_update(request, pk):
    line = get_object_or_404(
        FulfillmentLine.objects.select_related(
            "order__transaction__customer", "inventory_item"
        ),
        pk=pk,
    )
    if request.method == "POST":
        form = FulfillmentLineForm(request.POST, instance=line, order=line.order)
        if form.is_valid():
            form.save()
            messages.success(request, "Fulfillment allocation updated.")
            return redirect("transaction_detail", pk=line.order.transaction.pk)
    else:
        form = FulfillmentLineForm(instance=line, order=line.order)
    return render(
        request,
        "logistics/fulfillment/line_form.html",
        {
            "form": form,
            "title": "Update Warehouse Allocation",
            "order": line.order,
            "transaction": line.order.transaction,
            "line": line,
        },
    )


@login_required
@procurement_required
def shipment_leg_create(request, order_pk):
    order = get_object_or_404(
        FulfillmentOrder.objects.select_related("transaction__customer"), pk=order_pk
    )
    if request.method == "POST":
        form = ShipmentLegForm(request.POST)
        if form.is_valid():
            leg = form.save(commit=False)
            leg.order = order
            leg.created_by = request.user
            leg.save()
            messages.success(request, "Shipment leg added.")
            return redirect("transaction_detail", pk=order.transaction.pk)
    else:
        initial = {"sequence": order.legs.count() + 1}
        form = ShipmentLegForm(initial=initial)
    return render(
        request,
        "logistics/fulfillment/leg_form.html",
        {
            "form": form,
            "title": "Add Shipment Leg",
            "order": order,
            "transaction": order.transaction,
        },
    )


@login_required
@procurement_required
def shipment_leg_update(request, pk):
    leg = get_object_or_404(
        ShipmentLeg.objects.select_related("order__transaction__customer"), pk=pk
    )
    if request.method == "POST":
        form = ShipmentLegForm(request.POST, instance=leg)
        if form.is_valid():
            form.save()
            messages.success(request, "Shipment leg updated.")
            return redirect("transaction_detail", pk=leg.order.transaction.pk)
    else:
        form = ShipmentLegForm(instance=leg)
    return render(
        request,
        "logistics/fulfillment/leg_form.html",
        {
            "form": form,
            "title": "Update Shipment Leg",
            "order": leg.order,
            "transaction": leg.order.transaction,
            "leg": leg,
        },
    )


@login_required
@procurement_required
def supplier_create(request):
    if request.method != "POST":
        return redirect("supplier_list")
    form = SupplierForm(request.POST)
    if form.is_valid():
        supplier = form.save(commit=False)
        supplier.created_by = request.user
        supplier.save()
        messages.success(request, f"Supplier {supplier.name} added")
    else:
        messages.error(request, "Could not add supplier. Check the supplier details.")
    next_url = request.POST.get("next")
    if next_url == "inventory_list":
        return redirect("inventory_list")
    return redirect("supplier_list")


@login_required
@procurement_required
def supplier_list(request):
    suppliers = Supplier.objects.select_related("created_by").prefetch_related(
        "products"
    )
    search = request.GET.get("search", "").strip()
    if search:
        suppliers = suppliers.filter(
            Q(name__icontains=search)
            | Q(contact_person__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
            | Q(supplies__icontains=search)
            | Q(products__product_name__icontains=search)
        )
    suppliers = suppliers.distinct()
    page_obj, query_string, page_range = paginate_queryset(request, suppliers)
    return render(
        request,
        "logistics/suppliers/list.html",
        {
            "suppliers": page_obj,
            "supplier_form": SupplierForm(),
            "search": search,
            "page_obj": page_obj,
            "query_string": query_string,
            "page_range": page_range,
        },
    )


@login_required
@procurement_required
def supplier_update(request, pk):
    supplier = get_object_or_404(Supplier.objects.prefetch_related("products"), pk=pk)
    if request.method == "POST":
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, "Supplier updated")
            return redirect("supplier_list")
    else:
        form = SupplierForm(instance=supplier)
    return render(
        request,
        "logistics/suppliers/form.html",
        {
            "form": form,
            "title": "Update Supplier",
            "supplier": supplier,
            "product_form": SupplierProductForm(),
            "products": supplier.products.all(),
        },
    )


@login_required
@procurement_required
def supplier_product_create(request, supplier_pk):
    supplier = get_object_or_404(Supplier, pk=supplier_pk)
    if request.method != "POST":
        return redirect("supplier_update", pk=supplier.pk)

    # Support both single-row (old form) and multi-row array submission
    names = request.POST.getlist("product_name[]")
    if names:
        # Multi-row path: iterate parallel arrays
        specs = request.POST.getlist("specifications[]")
        moqs = request.POST.getlist("min_order_quantity[]")
        uprices = request.POST.getlist("unit_price[]")
        rprices = request.POST.getlist("resale_price[]")
        notes_l = request.POST.getlist("notes[]")
        saved = 0
        for i, name in enumerate(names):
            name = name.strip()
            if not name:
                continue

            def _dec(lst, idx):
                try:
                    v = lst[idx].strip()
                    return v if v else None
                except IndexError:
                    return None

            SupplierProduct.objects.create(
                supplier=supplier,
                created_by=request.user,
                product_name=name,
                specifications=specs[i].strip() if i < len(specs) else "",
                min_order_quantity=_dec(moqs, i),
                unit_price=_dec(uprices, i),
                resale_price=_dec(rprices, i),
                notes=notes_l[i].strip() if i < len(notes_l) else "",
            )
            saved += 1
        if saved:
            messages.success(request, f"{saved} product(s) added.")
        else:
            messages.warning(request, "No products saved — product name is required.")
    else:
        # Single-row legacy path
        form = SupplierProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.supplier = supplier
            product.created_by = request.user
            product.save()
            messages.success(request, "Supplier product added")
        else:
            messages.error(request, "Could not add product. Check the product details.")
    return redirect("supplier_update", pk=supplier.pk)


@login_required
@procurement_required
def supplier_product_delete(request, supplier_pk, product_pk):
    supplier = get_object_or_404(Supplier, pk=supplier_pk)
    product = get_object_or_404(SupplierProduct, pk=product_pk, supplier=supplier)
    if request.method == "POST":
        product.delete()
        messages.success(request, "Supplier product removed")
    return redirect("supplier_update", pk=supplier.pk)


@login_required
@procurement_required
def sourcing_update(request, pk):
    sourcing = get_object_or_404(Sourcing, pk=pk)
    pi_document = (
        sourcing.transaction.documents.filter(document_type="CLIENT_PI")
        .order_by("-timestamp")
        .first()
    )
    if request.method == "POST":
        form = SourcingForm(request.POST, instance=sourcing)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.created_by = request.user
            updated.save()
            action = request.POST.get("submit_action")
            if action == "open_proforma":
                validity_date = (request.POST.get("validity_date") or "").strip()
                messages.success(
                    request, "Sourcing record updated. Opening proforma form."
                )
                target = f"{reverse('proforma_create')}?from_sourcing={sourcing.pk}"
                if validity_date:
                    target += f"&validity_date={validity_date}"
                return redirect(target)
            messages.success(request, "Sourcing record updated")
            return redirect("sourcing_update", pk=sourcing.pk)
    else:
        form = SourcingForm(instance=sourcing)
    return render(
        request,
        "logistics/sourcing/form.html",
        {
            "form": form,
            "title": "Update Sourcing Record",
            "record": sourcing,
            "pi_document": pi_document,
            "transaction": sourcing.transaction,
        },
    )


@login_required
@procurement_required
def sourcing_pdf(request, pk):
    sourcing = get_object_or_404(
        Sourcing.objects.select_related("transaction__customer", "created_by"), pk=pk
    )
    form = SourcingForm(instance=sourcing)
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="sourcing_worksheet_{sourcing.transaction.transaction_id}.pdf"'
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=24,
        rightMargin=24,
        topMargin=28,
        bottomMargin=24,
    )
    styles = getSampleStyleSheet()
    story = []

    story.append(
        Paragraph(
            f"<b>GMI TERRALINK Sourcing Worksheet</b> - {sourcing.transaction.transaction_id}",
            styles["Title"],
        )
    )
    story.append(
        Paragraph(
            (
                f"Client: <b>{sourcing.transaction.customer.name}</b><br/>"
                f"Prepared by: {sourcing.created_by.get_full_name() or sourcing.created_by.username}"
            ),
            styles["BodyText"],
        )
    )
    story.append(Spacer(1, 12))

    table_data = [
        [
            "#",
            "Item",
            "Qty",
            "Unit",
            "A Supplier",
            "A Contact",
            "A Cost",
            "B Supplier",
            "B Contact",
            "B Cost",
            "C Supplier",
            "C Contact",
            "C Cost",
            "Preferred",
            "Notes",
        ]
    ]
    body_style = styles["BodyText"]
    body_style.fontSize = 7
    body_style.leading = 9

    for row in form.item_rows:
        preferred_quote = str(row.get("preferred_quote") or "").strip()
        cheapest_quote = str(row.get("cheapest_quote") or "").strip()

        def _cost_with_marker(quote_key):
            value = row.get(f"quote_{quote_key}_unit_price") or ""
            marker = ""
            if str(quote_key) == cheapest_quote and value:
                marker += "*"
            if str(quote_key) == preferred_quote and value:
                marker += "P"
            return f"{value} {marker}".strip()

        table_data.append(
            [
                str(row.get("index") or ""),
                Paragraph(row.get("name") or "", body_style),
                row.get("quantity") or "",
                row.get("unit") or "",
                Paragraph(row.get("quote_1_supplier_name") or "", body_style),
                Paragraph(row.get("quote_1_supplier_contact") or "", body_style),
                _cost_with_marker("1"),
                Paragraph(row.get("quote_2_supplier_name") or "", body_style),
                Paragraph(row.get("quote_2_supplier_contact") or "", body_style),
                _cost_with_marker("2"),
                Paragraph(row.get("quote_3_supplier_name") or "", body_style),
                Paragraph(row.get("quote_3_supplier_contact") or "", body_style),
                _cost_with_marker("3"),
                (
                    "A"
                    if preferred_quote == "1"
                    else (
                        "B"
                        if preferred_quote == "2"
                        else "C" if preferred_quote == "3" else ""
                    )
                ),
                Paragraph(row.get("notes") or "", body_style),
            ]
        )

    quote_table = Table(
        table_data,
        repeatRows=1,
        colWidths=[20, 90, 30, 30, 58, 58, 34, 58, 58, 34, 58, 58, 34, 40, 70],
    )
    quote_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1efe9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#3f3a3a")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("LEADING", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d7d3c7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#fbfaf7")],
                ),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(quote_table)
    story.append(
        Paragraph(
            "<i>* = cheapest captured quote in row, P = preferred quote selected for proforma handoff.</i>",
            styles["BodyText"],
        )
    )

    if sourcing.notes:
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Notes / Terms / Conditions</b>", styles["Heading4"]))
        story.append(
            Paragraph((sourcing.notes or "").replace("\n", "<br/>"), styles["BodyText"])
        )

    doc.build(story)
    response.write(buffer.getvalue())
    buffer.close()
    return response


@login_required
@procurement_required
def sourcing_create(request):
    pi_document = None
    initial = {}

    from_doc_pk = request.GET.get("from_doc")
    transaction_pk = request.GET.get("transaction")

    if from_doc_pk:
        pi_document = (
            Document.objects.filter(pk=from_doc_pk, document_type="CLIENT_PI")
            .select_related("transaction__customer")
            .first()
        )
        if pi_document:
            initial = _build_sourcing_initial_from_document(pi_document)
    elif transaction_pk:
        initial["transaction"] = Transaction.objects.filter(pk=transaction_pk).first()

    if request.method == "POST":
        form = SourcingForm(request.POST)
        if form.is_valid():
            sourcing = form.save(commit=False)
            sourcing.created_by = request.user
            sourcing.save()
            action = request.POST.get("submit_action")
            if action == "open_proforma":
                validity_date = (request.POST.get("validity_date") or "").strip()
                messages.success(
                    request, "Sourcing record saved. Opening proforma form."
                )
                target = f"{reverse('proforma_create')}?from_sourcing={sourcing.pk}"
                if validity_date:
                    target += f"&validity_date={validity_date}"
                return redirect(target)
            messages.success(request, "Sourcing record created")
            return redirect("sourcing_update", pk=sourcing.pk)
    else:
        form = SourcingForm(initial=initial)

    transaction = None
    if pi_document:
        transaction = pi_document.transaction
    elif initial.get("transaction"):
        transaction = initial["transaction"]

    return render(
        request,
        "logistics/sourcing/form.html",
        {
            "form": form,
            "title": "Create Sourcing Record",
            "pi_document": pi_document,
            "transaction": transaction,
        },
    )


@login_required
@role_required("PROCUREMENT", "FINANCE", "DIRECTOR", "ADMIN")
def proforma_list(request):
    lane = _resolve_lane_with_path(request)
    proformas = _apply_proforma_lane(
        ProformaInvoice.objects.select_related(
            "transaction__customer", "created_by", "loading"
        ),
        lane,
    )
    page_obj, query_string, page_range = paginate_queryset(request, proformas)
    return render(
        request,
        "logistics/invoicing/proforma_list.html",
        {
            "proformas": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "page_range": page_range,
            "active_lane": lane,
            "active_lane_label": _lane_label(lane),
            "can_switch_lane": _can_switch_lane(request.user),
        },
    )


@login_required
@role_required("PROCUREMENT", "FINANCE", "DIRECTOR", "ADMIN")
def proforma_create(request):
    """Single simple entry form for sourcing agents to create proforma invoices."""
    from decimal import Decimal, InvalidOperation
    import datetime

    pi_document = None
    sourcing_record = None
    prefill_items = []
    initial_transaction = None
    initial_notes = ""
    initial_validity_date = request.GET.get("validity_date", "")
    form_values = _build_proforma_form_values()

    from_doc_pk = request.GET.get("from_doc")
    from_sourcing_pk = request.GET.get("from_sourcing")
    transaction_pk = request.GET.get("transaction")

    if from_doc_pk:
        pi_document = (
            Document.objects.filter(pk=from_doc_pk, document_type="CLIENT_PI")
            .select_related("transaction__customer")
            .first()
        )
        if pi_document:
            initial_transaction = pi_document.transaction
            sd = pi_document.structured_data or {}
            if sd.get("items"):
                for it in sd["items"]:
                    name = it.get("name") or it.get("description") or ""
                    if name:
                        prefill_items.append(
                            {
                                "description": name,
                                "quantity": "1",
                                "unit_price": "",
                                "sales_price": "",
                            }
                        )
            initial_notes = build_sourcing_notes(sd) if sd else ""
    elif from_sourcing_pk:
        sourcing_record = (
            Sourcing.objects.filter(pk=from_sourcing_pk)
            .select_related("transaction__customer")
            .first()
        )
        if sourcing_record:
            initial_transaction = sourcing_record.transaction
            prefill_items = _prefill_proforma_items_from_sourcing(sourcing_record)
            initial_notes = sourcing_record.notes or ""
    elif transaction_pk:
        from .models import Transaction as Txn

        initial_transaction = Txn.objects.filter(pk=transaction_pk).first()

    if request.method == "POST":
        errors = []
        transaction_id = request.POST.get("transaction")
        validity_date_raw = request.POST.get("validity_date", "").strip()
        form_values = _build_proforma_form_values(post_data=request.POST)

        if not transaction_id:
            errors.append("Transaction is required.")

        # Parse item rows
        descs = request.POST.getlist("item_desc[]")
        qtys = request.POST.getlist("item_qty[]")
        unit_prices = request.POST.getlist("item_unit_price[]")
        sales_prices = request.POST.getlist("item_sales_price[]")

        items = []
        subtotal = Decimal("0")
        for desc, qty, unit_price_raw, sales_price_raw in zip(
            descs, qtys, unit_prices, sales_prices
        ):
            desc = desc.strip()
            if not desc:
                continue
            try:
                qty_d = Decimal(qty.strip() or "1")
                unit_price_d = Decimal(unit_price_raw.strip() or "0")
                sales_price_d = Decimal(sales_price_raw.strip() or "0")
            except InvalidOperation:
                continue
            line_total = qty_d * unit_price_d
            sales_price_d = line_total
            subtotal += line_total
            items.append(
                {
                    "description": desc,
                    "quantity": str(qty_d),
                    "unit_price": float(unit_price_d),
                    "sales_price": float(sales_price_d),
                    "total": float(line_total),
                }
            )

        if not items:
            errors.append("Add at least one item.")

        fee_values, fee_errors = _parse_quote_fees(request.POST)
        errors.extend(fee_errors)

        # Parse validity date
        validity_date = None
        if validity_date_raw:
            try:
                validity_date = datetime.date.fromisoformat(validity_date_raw)
            except ValueError:
                errors.append("Invalid validity date.")
        if not validity_date:
            validity_date = datetime.date.today() + datetime.timedelta(days=30)

        if not errors:
            try:
                txn = Transaction.objects.get(pk=transaction_id)
            except Transaction.DoesNotExist:
                errors.append("Transaction not found.")

        if not errors:
            proforma = ProformaInvoice.objects.create(
                transaction=txn,
                items=items,
                subtotal=subtotal,
                sourcing_fee=fee_values["sourcing_fee"],
                handling_fee=fee_values["handling_fee"],
                shipping_fee=fee_values["shipping_fee"],
                validity_date=validity_date,
                status="DRAFT",
                created_by=request.user,
            )
            Transaction.objects.filter(
                pk=txn.pk,
                status__in=["RECEIVED", "CLEANED", "SENT_TO_SOURCING", "QUOTED"],
            ).update(status="PROFORMA_CREATED")
            _notify_roles(
                title="Proforma invoice created",
                message=(
                    f"Proforma invoice PI-{proforma.pk} was created for transaction "
                    f"{txn.transaction_id}."
                ),
                link=reverse(
                    _proforma_route_name(proforma, "detail"),
                    kwargs={"pk": proforma.pk},
                ),
                category="invoice",
            )
            messages.success(request, "Proforma Invoice created successfully.")
            fulfillment = FulfillmentOrder.objects.filter(transaction=txn).first()
            if fulfillment:
                return redirect("fulfillment_order_update", pk=fulfillment.pk)
            return redirect(_proforma_route_name(proforma, "detail"), pk=proforma.pk)
        else:
            for e in errors:
                messages.error(request, e)

    transactions = Transaction.objects.select_related("customer").order_by(
        "-created_at"
    )
    return render(
        request,
        "logistics/invoicing/proforma_form.html",
        {
            "pi_document": pi_document,
            "sourcing_record": sourcing_record,
            "prefill_items": prefill_items,
            "initial_transaction": initial_transaction,
            "initial_notes": initial_notes,
            "initial_validity_date": initial_validity_date,
            "form_values": form_values,
            "transactions": transactions,
            "title": "Create Proforma Invoice",
        },
    )


@login_required
@role_required("PROCUREMENT", "FINANCE", "DIRECTOR", "ADMIN")
def proforma_detail(request, pk):
    proforma = get_object_or_404(
        ProformaInvoice.objects.select_related(
            "transaction__customer", "created_by", "loading"
        ),
        pk=pk,
    )
    canonical = _canonical_route_redirect(
        request, _proforma_route_name(proforma, "detail"), pk=proforma.pk
    )
    if canonical:
        return canonical
    final_invoice = proforma.transaction.final_invoices.order_by("-created_at").first()
    return render(
        request,
        "logistics/invoicing/proforma_detail.html",
        {"proforma": proforma, "final_invoice": final_invoice},
    )


@login_required
@role_required("PROCUREMENT", "FINANCE", "DIRECTOR", "ADMIN")
def proforma_update(request, pk):
    """Edit a draft proforma invoice using the same simplified entry template."""
    from decimal import Decimal, InvalidOperation
    import datetime

    proforma = get_object_or_404(ProformaInvoice, pk=pk)
    canonical = _canonical_route_redirect(
        request, _proforma_route_name(proforma, "update"), pk=proforma.pk
    )
    if canonical and request.method != "POST":
        return canonical
    is_freight = bool(proforma.loading_id)
    form_values = _build_proforma_form_values(proforma=proforma)
    if proforma.status == "SENT":
        messages.error(request, "Sent proformas cannot be edited.")
        return redirect(_proforma_route_name(proforma, "detail"), pk=pk)

    if request.method == "POST":
        errors = []
        validity_date_raw = request.POST.get("validity_date", "").strip()
        form_values = _build_proforma_form_values(post_data=request.POST)

        descs = request.POST.getlist("item_desc[]")
        qtys = request.POST.getlist("item_qty[]")
        unit_prices = request.POST.getlist("item_unit_price[]")
        sales_prices = request.POST.getlist("item_sales_price[]")
        units = request.POST.getlist("item_unit[]")

        items = []
        subtotal = Decimal("0")
        zipped = zip(
            descs,
            qtys,
            unit_prices,
            sales_prices,
            units if units else [""] * len(descs),
        )
        for desc, qty, unit_price_raw, sales_price_raw, item_unit in zipped:
            desc = desc.strip()
            if not desc:
                continue
            try:
                qty_d = Decimal(qty.strip() or "1")
                unit_price_d = Decimal(unit_price_raw.strip() or "0")
                sales_price_d = Decimal(sales_price_raw.strip() or "0")
            except InvalidOperation:
                continue
            line_total = qty_d * unit_price_d
            sales_price_d = line_total
            subtotal += line_total
            item_dict = {
                "description": desc,
                "quantity": str(qty_d),
                "unit_price": float(unit_price_d),
                "sales_price": float(sales_price_d),
                "total": float(line_total),
            }
            if item_unit:
                item_dict["unit"] = item_unit.strip()
            items.append(item_dict)

        fee_values, fee_errors = _parse_quote_fees(request.POST)
        errors.extend(fee_errors)

        validity_date = proforma.validity_date
        if validity_date_raw:
            try:
                validity_date = datetime.date.fromisoformat(validity_date_raw)
            except ValueError:
                errors.append("Invalid validity date.")

        if not errors:
            proforma.items = items
            proforma.subtotal = subtotal
            proforma.sourcing_fee = fee_values["sourcing_fee"]
            proforma.handling_fee = fee_values["handling_fee"]
            proforma.shipping_fee = fee_values["shipping_fee"]
            proforma.validity_date = validity_date
            proforma.save()
            messages.success(request, "Proforma Invoice updated.")
            fulfillment = FulfillmentOrder.objects.filter(
                transaction=proforma.transaction
            ).first()
            if fulfillment:
                return redirect("fulfillment_order_update", pk=fulfillment.pk)
            return redirect(_proforma_route_name(proforma, "detail"), pk=pk)
        else:
            for e in errors:
                messages.error(request, e)

    transactions = Transaction.objects.select_related("customer").order_by(
        "-created_at"
    )
    return render(
        request,
        "logistics/invoicing/proforma_form.html",
        {
            "proforma": proforma,
            "form_values": form_values,
            "initial_transaction": proforma.transaction,
            "transactions": transactions,
            "title": "Edit Proforma Invoice",
            "is_freight": is_freight,
            "loading": proforma.loading,
        },
    )


@login_required
@role_required("PROCUREMENT", "FINANCE", "DIRECTOR", "ADMIN")
def proforma_confirm(request, pk):
    """Confirm a proforma and convert it into a client-facing invoice."""
    from decimal import Decimal

    proforma = get_object_or_404(ProformaInvoice, pk=pk)
    canonical = _canonical_route_redirect(
        request, _proforma_route_name(proforma, "confirm"), pk=proforma.pk
    )
    if canonical and request.method != "POST":
        return canonical
    if request.method == "POST":
        final_items = []
        subtotal = Decimal("0")
        for it in proforma.items or []:
            sp = Decimal(str(it.get("sales_price") or it.get("amount") or "0"))
            qty = Decimal(str(it.get("quantity") or "1"))
            line = sp * qty
            subtotal += line
            final_items.append(
                {
                    "description": it.get("description", ""),
                    "quantity": str(qty),
                    "amount": float(line),
                }
            )
        invoice = FinalInvoice.objects.create(
            transaction=proforma.transaction,
            loading=proforma.loading
            or getattr(proforma.transaction, "source_loading", None),
            items=final_items,
            subtotal=subtotal,
            sourcing_fee=proforma.sourcing_fee,
            shipping_cost=proforma.shipping_fee,
            service_fee=proforma.handling_fee,
            total_amount=subtotal,
            created_by=request.user,
        )
        proforma.status = "SENT"
        proforma.save(update_fields=["status"])
        Transaction.objects.filter(pk=proforma.transaction.pk).update(
            status="FINAL_INVOICE_CREATED"
        )
        _notify_roles(
            title="Final invoice generated",
            message=(
                f"Final invoice FI-{invoice.pk} was generated from proforma "
                f"PI-{proforma.pk} for transaction {proforma.transaction.transaction_id}."
            ),
            link=reverse(
                _final_invoice_route_name(invoice, "detail"), kwargs={"pk": invoice.pk}
            ),
            category="invoice",
        )
        messages.success(request, "Proforma confirmed. Invoice created.")
        return redirect(_final_invoice_route_name(invoice, "detail"), pk=invoice.pk)
    return render(
        request,
        "logistics/invoicing/proforma_confirm.html",
        {"proforma": proforma},
    )


def _build_final_invoice_items(post_data):
    """Parse final-invoice builder rows into stored line items and subtotal."""
    from decimal import Decimal, InvalidOperation

    descs = post_data.getlist("item_desc[]")
    qtys = post_data.getlist("item_qty[]")
    unit_prices = post_data.getlist("item_unit_price[]")

    items = []
    subtotal = Decimal("0")
    errors = []

    for index, (desc, qty_raw, unit_price_raw) in enumerate(
        zip(descs, qtys, unit_prices), start=1
    ):
        desc = (desc or "").strip()
        qty_raw = (qty_raw or "").strip()
        unit_price_raw = (unit_price_raw or "").strip()

        if not desc and not qty_raw and not unit_price_raw:
            continue
        if not desc:
            errors.append(f"Line {index}: description is required.")
            continue

        try:
            quantity = Decimal(qty_raw or "1")
            unit_price = Decimal(unit_price_raw or "0")
        except InvalidOperation:
            errors.append(f"Line {index}: quantity and unit price must be numbers.")
            continue

        if quantity < 0 or unit_price < 0:
            errors.append(f"Line {index}: quantity and unit price cannot be negative.")
            continue

        line_total = quantity * unit_price
        subtotal += line_total
        items.append(
            {
                "description": desc,
                "quantity": str(quantity),
                "unit_price": float(unit_price),
                "amount": float(line_total),
                "total": float(line_total),
            }
        )

    if not items:
        errors.append("Add at least one invoice item.")

    return items, subtotal, errors


def _build_final_invoice_form_context(
    *, invoice=None, post_data=None, title, initial_transaction_id=""
):
    transactions = Transaction.objects.select_related("customer").order_by(
        "-created_at"
    )

    if post_data is not None:
        line_items = []
        descs = post_data.getlist("item_desc[]")
        qtys = post_data.getlist("item_qty[]")
        unit_prices = post_data.getlist("item_unit_price[]")
        for desc, qty, unit_price in zip(descs, qtys, unit_prices):
            if not any(
                [(desc or "").strip(), (qty or "").strip(), (unit_price or "").strip()]
            ):
                continue
            line_items.append(
                {
                    "description": desc,
                    "quantity": qty or "1",
                    "unit_price": unit_price or "0",
                }
            )
        if not line_items:
            line_items = [{"description": "", "quantity": "1", "unit_price": "0"}]

        form_values = {
            "transaction_id": post_data.get("transaction", ""),
            "sourcing_fee": post_data.get("sourcing_fee", "0"),
            "shipping_cost": post_data.get("shipping_cost", "0"),
            "service_fee": post_data.get("service_fee", "0"),
            "currency": post_data.get("currency", "USD"),
            "shipping_mode": post_data.get("shipping_mode", "SEA"),
            "route": post_data.get("route", "China-Mombasa-Kampala"),
            "is_confirmed": bool(post_data.get("is_confirmed")),
        }
    elif invoice is not None:
        line_items = invoice.items or []
        if not line_items:
            line_items = [{"description": "", "quantity": "1", "unit_price": "0"}]
        form_values = {
            "transaction_id": str(invoice.transaction_id),
            "sourcing_fee": invoice.sourcing_fee,
            "shipping_cost": invoice.shipping_cost,
            "service_fee": invoice.service_fee,
            "currency": invoice.currency,
            "shipping_mode": invoice.shipping_mode,
            "route": invoice.route,
            "is_confirmed": invoice.is_confirmed,
        }
    else:
        line_items = [{"description": "", "quantity": "1", "unit_price": "0"}]
        form_values = {
            "transaction_id": str(initial_transaction_id or ""),
            "sourcing_fee": "0",
            "shipping_cost": "0",
            "service_fee": "0",
            "currency": "USD",
            "shipping_mode": "SEA",
            "route": "China-Mombasa-Kampala",
            "is_confirmed": False,
        }

    return {
        "invoice": invoice,
        "title": title,
        "transactions": transactions,
        "line_items": line_items,
        "form_values": form_values,
        "shipping_mode_choices": FinalInvoice.SHIPPING_MODE_CHOICES,
    }


@login_required
@role_required("PROCUREMENT", "FINANCE", "DIRECTOR", "ADMIN")
def proforma_pdf(request, pk):
    proforma = get_object_or_404(
        ProformaInvoice.objects.select_related(
            "transaction__customer", "created_by", "loading"
        ),
        pk=pk,
    )
    canonical = _canonical_route_redirect(
        request, _proforma_route_name(proforma, "pdf"), pk=proforma.pk
    )
    if canonical:
        return canonical
    pdf_data = proforma.generate_pdf()
    response = HttpResponse(pdf_data, content_type="application/pdf")
    department_prefix = "cargo" if proforma.loading_id else "sourcing"
    response["Content-Disposition"] = (
        f'attachment; filename="{department_prefix}_proforma_{proforma.transaction.transaction_id}.pdf"'
    )
    _notify_roles(
        title="Proforma PDF generated",
        message=(
            f"A PDF was generated for proforma PI-{proforma.pk} on transaction "
            f"{proforma.transaction.transaction_id}."
        ),
        link=reverse(
            _proforma_route_name(proforma, "detail"), kwargs={"pk": proforma.pk}
        ),
        category="document",
    )
    return response


@login_required
@role_required("PROCUREMENT", "FINANCE", "DIRECTOR", "ADMIN")
def final_invoice_list(request):
    lane = _resolve_lane_with_path(request)
    invoices = _apply_final_invoice_lane(
        FinalInvoice.objects.select_related(
            "transaction__customer", "created_by", "loading"
        ),
        lane,
    )
    page_obj, query_string, page_range = paginate_queryset(request, invoices)

    for inv in page_obj:
        total_paid = inv.payment_records.aggregate(total=Sum("amount"))["total"] or 0
        if total_paid <= 0:
            total_paid = (
                inv.transaction.payment_records.aggregate(total=Sum("amount"))["total"]
                or 0
            )
        balance = max((inv.total_amount or 0) - total_paid, 0)
        inv.total_paid_for_display = total_paid
        inv.balance_for_display = balance
        inv.can_edit_invoice = total_paid <= 0
        if total_paid > 0 and balance <= 0:
            inv.payment_status_label = "Paid"
            inv.payment_status_class = "bg-success"
        elif total_paid > 0:
            inv.payment_status_label = "Partial Payment"
            inv.payment_status_class = "bg-warning text-dark"
        else:
            inv.payment_status_label = "Unpaid"
            inv.payment_status_class = "bg-secondary"

    return render(
        request,
        "logistics/invoicing/final_list.html",
        {
            "invoices": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "page_range": page_range,
            "active_lane": lane,
            "active_lane_label": _lane_label(lane),
            "can_switch_lane": _can_switch_lane(request.user),
        },
    )


@login_required
@role_required("PROCUREMENT", "FINANCE", "DIRECTOR", "ADMIN")
def final_invoice_detail(request, pk):
    invoice = get_object_or_404(
        FinalInvoice.objects.select_related(
            "transaction__customer", "created_by", "loading"
        ),
        pk=pk,
    )
    canonical = _canonical_route_redirect(
        request, _final_invoice_route_name(invoice, "detail"), pk=invoice.pk
    )
    if canonical:
        return canonical
    total_paid = invoice.payment_records.aggregate(total=Sum("amount"))["total"] or 0
    if total_paid <= 0:
        total_paid = (
            invoice.transaction.payment_records.aggregate(total=Sum("amount"))["total"]
            or 0
        )
    purchase_orders_qs = invoice.transaction.purchase_orders.filter(
        Q(final_invoice=invoice) | Q(final_invoice__isnull=True)
    ).select_related("parent_po")
    purchase_order = (
        purchase_orders_qs.filter(parent_po__isnull=True)
        .order_by("-created_at")
        .first()
        or purchase_orders_qs.order_by("-created_at").first()
    )
    split_purchase_orders = purchase_orders_qs.filter(parent_po__isnull=False).order_by(
        "-created_at"
    )

    total_paid_decimal = total_paid or 0
    balance = max((invoice.total_amount or 0) - total_paid, 0)
    if total_paid_decimal > 0 and balance <= 0:
        payment_status_label = "Paid"
        payment_status_class = "bg-success"
    elif total_paid_decimal > 0:
        payment_status_label = "Partial Payment"
        payment_status_class = "bg-warning text-dark"
    else:
        payment_status_label = "Unpaid"
        payment_status_class = "bg-secondary"
    can_edit_invoice = total_paid_decimal <= 0

    can_generate_po = (
        total_paid_decimal >= (invoice.total_amount or 0) and purchase_order is None
    )
    return render(
        request,
        "logistics/invoicing/final_detail.html",
        {
            "invoice": invoice,
            "total_paid": total_paid,
            "balance": balance,
            "payment_status_label": payment_status_label,
            "payment_status_class": payment_status_class,
            "can_edit_invoice": can_edit_invoice,
            "purchase_order": purchase_order,
            "split_purchase_orders": split_purchase_orders,
            "can_generate_po": can_generate_po,
        },
    )


@login_required
@role_required("PROCUREMENT", "FINANCE", "DIRECTOR", "ADMIN")
def final_invoice_create(request):
    if request.method == "POST":
        from decimal import Decimal, InvalidOperation

        items, subtotal, errors = _build_final_invoice_items(request.POST)
        transaction_id = (request.POST.get("transaction") or "").strip()
        sourcing_fee_raw = (request.POST.get("sourcing_fee") or "0").strip()
        shipping_cost_raw = (request.POST.get("shipping_cost") or "0").strip()
        service_fee_raw = (request.POST.get("service_fee") or "0").strip()
        currency = (request.POST.get("currency") or "USD").strip() or "USD"
        shipping_mode = (request.POST.get("shipping_mode") or "SEA").strip() or "SEA"
        route = (
            request.POST.get("route") or "China-Mombasa-Kampala"
        ).strip() or "China-Mombasa-Kampala"
        is_confirmed = bool(request.POST.get("is_confirmed"))

        try:
            sourcing_fee = Decimal(sourcing_fee_raw or "0")
            shipping_cost = Decimal(shipping_cost_raw or "0")
            service_fee = Decimal(service_fee_raw or "0")
            if sourcing_fee < 0 or shipping_cost < 0 or service_fee < 0:
                raise InvalidOperation
        except InvalidOperation:
            errors.append(
                "Sourcing fee, shipping fee, and handling fee must be valid non-negative numbers."
            )

        txn = None
        if not transaction_id:
            errors.append("Select a transaction.")
        else:
            try:
                txn = Transaction.objects.get(pk=transaction_id)
            except Transaction.DoesNotExist:
                errors.append("Transaction not found.")

        if not errors:
            invoice = FinalInvoice.objects.create(
                transaction=txn,
                loading=getattr(txn, "source_loading", None),
                items=items,
                subtotal=subtotal,
                sourcing_fee=sourcing_fee,
                shipping_cost=shipping_cost,
                service_fee=service_fee,
                currency=currency,
                shipping_mode=shipping_mode,
                route=route,
                is_confirmed=is_confirmed,
                created_by=request.user,
            )
            Transaction.objects.filter(pk=invoice.transaction.pk).update(
                status="FINAL_INVOICE_CREATED"
            )
            _notify_roles(
                title="Final invoice created",
                message=(
                    f"Final invoice FI-{invoice.pk} was created for transaction "
                    f"{invoice.transaction.transaction_id}."
                ),
                link=reverse(
                    _final_invoice_route_name(invoice, "detail"),
                    kwargs={"pk": invoice.pk},
                ),
                category="invoice",
            )
            messages.success(request, "Final invoice created")
            return redirect(_final_invoice_route_name(invoice, "detail"), pk=invoice.pk)

        for error in errors:
            messages.error(request, error)
    else:
        transaction_pk = request.GET.get("transaction", "")
    return render(
        request,
        "logistics/invoicing/final_form.html",
        _build_final_invoice_form_context(
            post_data=request.POST if request.method == "POST" else None,
            title="Create Final Invoice",
            initial_transaction_id=transaction_pk if request.method != "POST" else "",
        ),
    )


@login_required
@role_required("PROCUREMENT", "FINANCE", "DIRECTOR", "ADMIN")
def final_invoice_update(request, pk):
    invoice = get_object_or_404(FinalInvoice, pk=pk)
    canonical = _canonical_route_redirect(
        request, _final_invoice_route_name(invoice, "update"), pk=invoice.pk
    )
    if canonical and request.method != "POST":
        return canonical
    locked_paid_total = (
        invoice.payment_records.aggregate(total=Sum("amount"))["total"] or 0
    )
    if locked_paid_total <= 0:
        locked_paid_total = (
            invoice.transaction.payment_records.aggregate(total=Sum("amount"))["total"]
            or 0
        )
    if locked_paid_total > 0:
        messages.error(
            request,
            "This invoice already has recorded payments and can no longer be edited.",
        )
        return redirect(_final_invoice_route_name(invoice, "detail"), pk=invoice.pk)

    if request.method == "POST":
        from decimal import Decimal, InvalidOperation

        items, subtotal, errors = _build_final_invoice_items(request.POST)
        transaction_id = (request.POST.get("transaction") or "").strip()
        sourcing_fee_raw = (request.POST.get("sourcing_fee") or "0").strip()
        shipping_cost_raw = (request.POST.get("shipping_cost") or "0").strip()
        service_fee_raw = (request.POST.get("service_fee") or "0").strip()
        currency = (request.POST.get("currency") or invoice.currency).strip() or "USD"
        shipping_mode = (
            request.POST.get("shipping_mode") or invoice.shipping_mode
        ).strip() or "SEA"
        route = (
            request.POST.get("route") or invoice.route
        ).strip() or "China-Mombasa-Kampala"
        is_confirmed = bool(request.POST.get("is_confirmed"))

        try:
            sourcing_fee = Decimal(sourcing_fee_raw or "0")
            shipping_cost = Decimal(shipping_cost_raw or "0")
            service_fee = Decimal(service_fee_raw or "0")
            if sourcing_fee < 0 or shipping_cost < 0 or service_fee < 0:
                raise InvalidOperation
        except InvalidOperation:
            errors.append(
                "Sourcing fee, shipping fee, and handling fee must be valid non-negative numbers."
            )

        txn = None
        if not transaction_id:
            errors.append("Select a transaction.")
        else:
            try:
                txn = Transaction.objects.get(pk=transaction_id)
            except Transaction.DoesNotExist:
                errors.append("Transaction not found.")

        if not errors:
            invoice.transaction = txn
            invoice.items = items
            invoice.subtotal = subtotal
            invoice.sourcing_fee = sourcing_fee
            invoice.shipping_cost = shipping_cost
            invoice.service_fee = service_fee
            invoice.currency = currency
            invoice.shipping_mode = shipping_mode
            invoice.route = route
            invoice.is_confirmed = is_confirmed
            invoice.created_by = request.user
            try:
                invoice.save()
            except ValidationError as exc:
                if hasattr(exc, "messages"):
                    errors.extend(exc.messages)
                else:
                    errors.append(str(exc))
            else:
                messages.success(request, "Final invoice updated")
                return redirect(
                    _final_invoice_route_name(invoice, "detail"), pk=invoice.pk
                )

        for error in errors:
            messages.error(request, error)
    return render(
        request,
        "logistics/invoicing/final_form.html",
        _build_final_invoice_form_context(
            invoice=invoice,
            post_data=request.POST if request.method == "POST" else None,
            title="Update Final Invoice",
        ),
    )


@login_required
@role_required("PROCUREMENT", "FINANCE", "DIRECTOR", "ADMIN")
def final_invoice_pdf(request, pk):
    invoice = get_object_or_404(
        FinalInvoice.objects.select_related("transaction__customer", "created_by"),
        pk=pk,
    )
    canonical = _canonical_route_redirect(
        request, _final_invoice_route_name(invoice, "pdf"), pk=invoice.pk
    )
    if canonical:
        return canonical
    pdf_data = invoice.generate_pdf()
    response = HttpResponse(pdf_data, content_type="application/pdf")
    department_prefix = "cargo" if invoice.loading_id else "sourcing"
    response["Content-Disposition"] = (
        f'attachment; filename="{department_prefix}_final_invoice_{invoice.transaction.transaction_id}.pdf"'
    )
    _notify_roles(
        title="Final invoice PDF generated",
        message=(
            f"A PDF was generated for final invoice FI-{invoice.pk} on transaction "
            f"{invoice.transaction.transaction_id}."
        ),
        link=reverse(
            _final_invoice_route_name(invoice, "detail"), kwargs={"pk": invoice.pk}
        ),
        category="document",
    )
    return response


def _ensure_purchase_order_for_transaction(transaction, user, invoice=None):
    """Create a base purchase order for a fully paid invoice/transaction."""
    if invoice is None:
        invoice = transaction.final_invoices.order_by(
            "-is_confirmed", "-created_at"
        ).first()
    existing = (
        transaction.purchase_orders.filter(
            parent_po__isnull=True,
            final_invoice=invoice,
        )
        .order_by("-created_at")
        .first()
    )
    if existing:
        return existing, False

    proforma = transaction.proforma_invoices.order_by("-created_at").first()
    if not invoice:
        return None, False

    purchase_order = PurchaseOrder.objects.create(
        transaction=transaction,
        proforma=proforma,
        final_invoice=invoice,
        supplier_name=(proforma.supplier_name if proforma else "Supplier Pending"),
        supplier_address=(proforma.supplier_address if proforma else ""),
        items=invoice.items,
        subtotal=invoice.subtotal,
        notes="Base purchase order generated from fully paid final invoice.",
        created_by=user,
    )
    return purchase_order, True


@login_required
@role_required("PROCUREMENT", "FINANCE", "DIRECTOR", "ADMIN")
def final_invoice_generate_purchase_order(request, pk):
    """Generate a base purchase order from a fully paid final invoice."""
    invoice = get_object_or_404(
        FinalInvoice.objects.select_related("transaction", "transaction__customer"),
        pk=pk,
    )
    canonical = _canonical_route_redirect(
        request, _final_invoice_route_name(invoice, "generate_po"), pk=invoice.pk
    )
    if canonical and request.method != "POST":
        return canonical
    total_paid = (
        invoice.transaction.payment_records.aggregate(total=Sum("amount"))["total"] or 0
    )
    if total_paid < (invoice.total_amount or 0):
        messages.error(
            request,
            "Invoice is not fully paid yet. Complete payment before generating a purchase order.",
        )
        return redirect(_final_invoice_route_name(invoice, "detail"), pk=invoice.pk)

    purchase_order, created = _ensure_purchase_order_for_transaction(
        invoice.transaction,
        request.user,
        invoice=invoice,
    )
    if purchase_order and created:
        messages.success(
            request,
            f"Purchase Order {purchase_order.po_number} generated from FI-{invoice.pk}.",
        )
    elif purchase_order:
        messages.info(
            request,
            f"Purchase Order {purchase_order.po_number} already exists for FI-{invoice.pk}.",
        )
    else:
        messages.error(request, "Unable to generate purchase order for this invoice.")
    return redirect(_final_invoice_route_name(invoice, "detail"), pk=invoice.pk)


def _parse_purchase_order_items(post_data):
    """Parse PO line items from request payload into normalized JSON rows."""
    from decimal import Decimal, InvalidOperation

    descs = post_data.getlist("item_desc[]")
    qtys = post_data.getlist("item_qty[]")
    unit_prices = post_data.getlist("item_unit_price[]")

    items = []
    subtotal = Decimal("0")
    for desc, qty_raw, unit_price_raw in zip(descs, qtys, unit_prices):
        description = (desc or "").strip()
        if not description:
            continue
        try:
            quantity = Decimal((qty_raw or "1").strip() or "1")
            unit_price = Decimal((unit_price_raw or "0").strip() or "0")
        except InvalidOperation:
            continue
        if quantity < 0 or unit_price < 0:
            continue
        line_total = quantity * unit_price
        subtotal += line_total
        items.append(
            {
                "description": description,
                "quantity": str(quantity),
                "unit_price": float(unit_price),
                "amount": float(line_total),
                "total": float(line_total),
            }
        )

    return items, subtotal


@login_required
@role_required("PROCUREMENT", "FINANCE", "DIRECTOR", "ADMIN")
def purchase_order_split_create(request, pk):
    """Create a supplier split purchase order linked to the same invoice details."""
    purchase_order = get_object_or_404(
        PurchaseOrder.objects.select_related(
            "transaction",
            "transaction__customer",
            "proforma",
            "final_invoice",
            "parent_po",
        ),
        pk=pk,
    )
    base_po = purchase_order.root_po
    invoice = (
        base_po.final_invoice
        or purchase_order.transaction.final_invoices.order_by(
            "-is_confirmed", "-created_at"
        ).first()
    )
    suppliers = Supplier.objects.all().order_by("name")

    if request.method == "POST":
        supplier_id = (request.POST.get("supplier_id") or "").strip()
        manual_supplier_name = (request.POST.get("supplier_name") or "").strip()
        manual_supplier_address = (request.POST.get("supplier_address") or "").strip()
        split_notes = (request.POST.get("notes") or "").strip()

        supplier_name = ""
        supplier_address = ""
        if supplier_id:
            supplier = get_object_or_404(Supplier, pk=supplier_id)
            supplier_name = supplier.name
            supplier_address = supplier.address or ""
        elif manual_supplier_name:
            supplier_name = manual_supplier_name
            supplier_address = manual_supplier_address
        else:
            messages.error(
                request,
                "Select a supplier or provide supplier name manually to create a split purchase order.",
            )
            return render(
                request,
                "logistics/invoicing/purchase_order_split_form.html",
                {
                    "purchase_order": purchase_order,
                    "base_po": base_po,
                    "invoice": invoice,
                    "suppliers": suppliers,
                },
            )

        split_po = PurchaseOrder.objects.create(
            transaction=base_po.transaction,
            proforma=base_po.proforma,
            final_invoice=invoice,
            parent_po=base_po,
            supplier_name=supplier_name,
            supplier_address=supplier_address,
            items=(invoice.items if invoice else base_po.items),
            subtotal=(invoice.subtotal if invoice else base_po.subtotal),
            notes=split_notes or f"Supplier split from base PO {base_po.po_number}.",
            created_by=request.user,
        )
        messages.success(
            request,
            f"Split purchase order {split_po.po_number} created. You can now edit supplier-specific items before sending.",
        )
        return redirect("purchase_order_update", pk=split_po.pk)

    return render(
        request,
        "logistics/invoicing/purchase_order_split_form.html",
        {
            "purchase_order": purchase_order,
            "base_po": base_po,
            "invoice": invoice,
            "suppliers": suppliers,
        },
    )


@login_required
@role_required("PROCUREMENT", "FINANCE", "DIRECTOR", "ADMIN")
def purchase_order_list(request):
    purchase_orders = PurchaseOrder.objects.select_related(
        "transaction__customer", "created_by", "parent_po", "final_invoice"
    )
    page_obj, query_string, page_range = paginate_queryset(request, purchase_orders)
    return render(
        request,
        "logistics/invoicing/purchase_order_list.html",
        {
            "purchase_orders": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "page_range": page_range,
        },
    )


@login_required
@role_required("PROCUREMENT", "FINANCE", "DIRECTOR", "ADMIN")
def purchase_order_update(request, pk):
    """Edit a base or split PO so each supplier version can be tailored independently."""
    purchase_order = get_object_or_404(
        PurchaseOrder.objects.select_related(
            "transaction__customer",
            "created_by",
            "parent_po",
            "final_invoice",
            "proforma",
        ),
        pk=pk,
    )
    suppliers = Supplier.objects.all().order_by("name")

    if request.method == "POST":
        supplier_id = (request.POST.get("supplier_id") or "").strip()
        supplier_name = (request.POST.get("supplier_name") or "").strip()
        supplier_address = (request.POST.get("supplier_address") or "").strip()
        notes = (request.POST.get("notes") or "").strip()
        status = (request.POST.get("status") or "PENDING").strip().upper()

        if supplier_id:
            supplier = get_object_or_404(Supplier, pk=supplier_id)
            supplier_name = supplier.name
            supplier_address = supplier.address or ""

        if not supplier_name:
            messages.error(request, "Supplier name is required.")
            return render(
                request,
                "logistics/invoicing/purchase_order_form.html",
                {
                    "purchase_order": purchase_order,
                    "suppliers": suppliers,
                    "title": f"Edit Purchase Order {purchase_order.po_number}",
                },
            )

        items, subtotal = _parse_purchase_order_items(request.POST)
        if not items:
            messages.error(request, "Add at least one valid line item for this PO.")
            return render(
                request,
                "logistics/invoicing/purchase_order_form.html",
                {
                    "purchase_order": purchase_order,
                    "suppliers": suppliers,
                    "title": f"Edit Purchase Order {purchase_order.po_number}",
                },
            )

        valid_statuses = {choice[0] for choice in PurchaseOrder.STATUS_CHOICES}
        if status not in valid_statuses:
            status = purchase_order.status

        purchase_order.supplier_name = supplier_name
        purchase_order.supplier_address = supplier_address
        purchase_order.items = items
        purchase_order.subtotal = subtotal
        purchase_order.notes = notes
        purchase_order.status = status
        purchase_order.save(
            update_fields=[
                "supplier_name",
                "supplier_address",
                "items",
                "subtotal",
                "notes",
                "status",
                "updated_at",
            ]
        )
        messages.success(
            request,
            f"Purchase Order {purchase_order.po_number} updated for supplier dispatch.",
        )
        return redirect("purchase_order_detail", pk=purchase_order.pk)

    return render(
        request,
        "logistics/invoicing/purchase_order_form.html",
        {
            "purchase_order": purchase_order,
            "suppliers": suppliers,
            "title": f"Edit Purchase Order {purchase_order.po_number}",
        },
    )


@login_required
def purchase_order_detail(request, pk):
    purchase_order = get_object_or_404(
        PurchaseOrder.objects.select_related(
            "transaction__customer",
            "created_by",
            "parent_po",
            "final_invoice",
        ),
        pk=pk,
    )
    base_po = purchase_order.root_po
    sibling_splits = base_po.split_purchase_orders.select_related(
        "created_by"
    ).order_by("-created_at")
    can_start_invoice_fulfillment = False
    if purchase_order.final_invoice_id:
        total_paid = (
            purchase_order.final_invoice.transaction.payment_records.aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )
        can_start_invoice_fulfillment = total_paid >= (
            purchase_order.final_invoice.total_amount or 0
        )
    return render(
        request,
        "logistics/invoicing/purchase_order_detail.html",
        {
            "purchase_order": purchase_order,
            "base_po": base_po,
            "sibling_splits": sibling_splits,
            "can_start_invoice_fulfillment": can_start_invoice_fulfillment,
            "supplier_payments": purchase_order.supplier_payments.select_related(
                "created_by"
            ).order_by("-paid_at", "-id"),
            "supplier_total_paid": purchase_order.supplier_payments.aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00"),
            "supplier_balance_due": max(
                (purchase_order.subtotal or Decimal("0.00"))
                - (
                    purchase_order.supplier_payments.aggregate(total=Sum("amount"))[
                        "total"
                    ]
                    or Decimal("0.00")
                ),
                Decimal("0.00"),
            ),
        },
    )


def _pdf_report_response(filename, title, headers, rows):
    """Render tabular data into a downloadable PDF report."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=30,
        rightMargin=30,
        topMargin=30,
        bottomMargin=30,
    )
    styles = getSampleStyleSheet()
    elements = []
    elements.append(Paragraph(f"<b>GMI TERRALINK — {title}</b>", styles["Title"]))
    elements.append(Spacer(1, 10))

    table_data = [headers] + [
        [str(cell) if cell is not None else "" for cell in row] for row in rows
    ]
    col_count = len(headers)
    col_width = (landscape(A4)[0] - 60) / max(col_count, 1)
    table = Table(table_data, colWidths=[col_width] * max(col_count, 1), repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#eaf4fb")],
                ),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _format_datetime(value):
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


def _serialize_compact_json(value):
    if value in (None, "", [], {}):
        return ""
    return json.dumps(value, ensure_ascii=True)


def _count_collection(value):
    if isinstance(value, (list, tuple, dict)):
        return len(value)
    return 0


@login_required
@director_required
def reports_dashboard(request):
    can_view_financial_totals = request.user.is_superuser or request.user.role in {
        "ADMIN",
        "DIRECTOR",
        "FINANCE",
    }
    totals = (
        DirectorReportingService.financial_totals()
        if can_view_financial_totals
        else {"total_revenue": 0, "outstanding_balance": 0}
    )
    conversion = DirectorReportingService.conversion_rate()
    top_clients = DirectorReportingService.top_clients()
    profit_estimate = DirectorReportingService.profit_estimate()
    trend_labels, trend_values = DirectorReportingService.revenue_trend()
    status_labels, status_values = (
        DirectorReportingService.transaction_status_breakdown()
    )
    trade_summary = DirectorReportingService.trade_activity_summary()
    trade_pipeline_labels, trade_pipeline_values = (
        DirectorReportingService.trade_pipeline_breakdown()
    )
    supplier_activity = DirectorReportingService.sourcing_activity_by_supplier()
    supplier_labels, supplier_values = (
        DirectorReportingService.sourcing_activity_by_supplier_chart()
    )
    recent_sourcing_activity = DirectorReportingService.recent_sourcing_activity()
    commission_totals = DirectorReportingService.commission_totals()
    context = {
        "total_revenue": totals["total_revenue"],
        "outstanding_balance": totals["outstanding_balance"],
        "active_shipments": DirectorReportingService.active_shipments_count(),
        "profit_estimate": profit_estimate,
        "conversion_rate": conversion["rate"],
        "conversion_inquiries": conversion["inquiries"],
        "conversion_confirmed": conversion["confirmed"],
        "top_clients": top_clients,
        "trade_summary": trade_summary,
        "supplier_activity": supplier_activity,
        "recent_sourcing_activity": recent_sourcing_activity,
        "trend_labels_json": json.dumps(trend_labels),
        "trend_values_json": json.dumps(trend_values),
        "status_labels_json": json.dumps(status_labels),
        "status_values_json": json.dumps(status_values),
        "trade_pipeline_labels_json": json.dumps(trade_pipeline_labels),
        "trade_pipeline_values_json": json.dumps(trade_pipeline_values),
        "supplier_labels_json": json.dumps(supplier_labels),
        "supplier_values_json": json.dumps(supplier_values),
        "commission_totals": commission_totals,
    }
    return render(request, "logistics/reports/dashboard.html", context)


@login_required
@director_required
def export_clients_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="clients_report.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Client ID",
            "Name",
            "Contact Person",
            "Phone",
            "Address",
            "Date Registered",
            "Remarks",
        ]
    )
    for client in Client.objects.all():
        writer.writerow(
            [
                client.client_id,
                client.name,
                client.contact_person,
                client.phone,
                client.address,
                client.date_registered.strftime("%Y-%m-%d %H:%M"),
                client.remarks or "",
            ]
        )
    log_audit("client", "export", 0, "CSV Export", request.user)
    return response


@login_required
@director_required
def export_clients_pdf(request):
    headers = [
        "Client ID",
        "Name",
        "Contact Person",
        "Phone",
        "Address",
        "Date Registered",
        "Remarks",
    ]
    rows = [
        [
            client.client_id,
            client.name,
            client.contact_person,
            client.phone,
            client.address,
            client.date_registered.strftime("%Y-%m-%d %H:%M"),
            client.remarks or "",
        ]
        for client in Client.objects.all()
    ]
    response = _pdf_report_response(
        "clients_report.pdf", "Clients Report", headers, rows
    )
    log_audit("client", "export", 0, "PDF Export", request.user)
    return response


@login_required
@director_required
def export_shipments_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="shipments_report.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Loading ID",
            "Client",
            "Loading Date",
            "Item Description",
            "Weight (KG)",
            "Container Number",
            "Container Size",
            "Origin",
            "Destination",
        ]
    )
    for loading in Loading.objects.select_related("client"):
        writer.writerow(
            [
                loading.loading_id,
                loading.client.name,
                loading.loading_date.strftime("%Y-%m-%d %H:%M"),
                loading.item_description,
                loading.weight,
                loading.container_number,
                loading.get_container_size_display() if loading.container_size else "",
                loading.origin,
                loading.destination,
            ]
        )
    log_audit("loading", "export", 0, "CSV Export", request.user)
    return response


@login_required
@director_required
def export_shipments_pdf(request):
    headers = [
        "Loading ID",
        "Client",
        "Loading Date",
        "Item Description",
        "Weight (KG)",
        "Container Number",
        "Container Size",
        "Origin",
        "Destination",
    ]
    rows = [
        [
            loading.loading_id,
            loading.client.name,
            loading.loading_date.strftime("%Y-%m-%d %H:%M"),
            loading.item_description,
            loading.weight or "",
            loading.container_number,
            loading.get_container_size_display() if loading.container_size else "",
            loading.origin,
            loading.destination,
        ]
        for loading in Loading.objects.select_related("client")
    ]
    response = _pdf_report_response(
        "shipments_report.pdf", "Shipments Report", headers, rows
    )
    log_audit("loading", "export", 0, "PDF Export", request.user)
    return response


@login_required
@director_required
def export_payments_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="payments_report.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Loading ID",
            "Client",
            "Amount Charged",
            "Amount Paid",
            "Balance",
            "Payment Date",
            "Payment Method",
            "Receipt Number",
        ]
    )
    for payment in Payment.objects.select_related("loading__client"):
        writer.writerow(
            [
                payment.loading.loading_id,
                payment.loading.client.name,
                payment.amount_charged,
                payment.amount_paid,
                payment.balance,
                (
                    payment.payment_date.strftime("%Y-%m-%d %H:%M")
                    if payment.payment_date
                    else ""
                ),
                payment.get_payment_method_display() if payment.payment_method else "",
                payment.receipt_number or "",
            ]
        )
    log_audit("payment", "export", 0, "CSV Export", request.user)
    return response


@login_required
@director_required
def export_payments_pdf(request):
    headers = [
        "Loading ID",
        "Client",
        "Amount Charged",
        "Amount Paid",
        "Balance",
        "Payment Date",
        "Payment Method",
        "Receipt Number",
    ]
    rows = [
        [
            payment.loading.loading_id,
            payment.loading.client.name,
            f"${payment.amount_charged:,.2f}",
            f"${payment.amount_paid:,.2f}",
            f"${payment.balance:,.2f}",
            (
                payment.payment_date.strftime("%Y-%m-%d %H:%M")
                if payment.payment_date
                else ""
            ),
            payment.get_payment_method_display() if payment.payment_method else "",
            payment.receipt_number or "",
        ]
        for payment in Payment.objects.select_related("loading__client")
    ]
    response = _pdf_report_response(
        "payments_report.pdf", "Payments Report", headers, rows
    )
    log_audit("payment", "export", 0, "PDF Export", request.user)
    return response


@login_required
@director_required
def export_containers_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        'attachment; filename="container_returns_report.csv"'
    )
    writer = csv.writer(response)
    writer.writerow(
        [
            "Container Number",
            "Container Size",
            "Loading ID",
            "Client",
            "Return Date",
            "Condition",
            "Status",
            "Remarks",
        ]
    )
    for container in ContainerReturn.objects.select_related("loading__client"):
        size_display = (
            container.get_container_size_display()
            if container.container_size
            else (
                container.loading.get_container_size_display()
                if container.loading.container_size
                else ""
            )
        )
        writer.writerow(
            [
                container.container_number,
                size_display,
                container.loading.loading_id,
                container.loading.client.name,
                container.return_date.strftime("%Y-%m-%d %H:%M"),
                container.get_condition_display(),
                container.get_status_display(),
                container.remarks or "",
            ]
        )
    log_audit("container_return", "export", 0, "CSV Export", request.user)
    return response


@login_required
@director_required
def export_containers_pdf(request):
    headers = [
        "Container Number",
        "Container Size",
        "Loading ID",
        "Client",
        "Return Date",
        "Condition",
        "Status",
        "Remarks",
    ]
    rows = []
    for container in ContainerReturn.objects.select_related("loading__client"):
        size_display = (
            container.get_container_size_display()
            if container.container_size
            else (
                container.loading.get_container_size_display()
                if container.loading.container_size
                else ""
            )
        )
        rows.append(
            [
                container.container_number,
                size_display,
                container.loading.loading_id,
                container.loading.client.name,
                container.return_date.strftime("%Y-%m-%d %H:%M"),
                container.get_condition_display(),
                container.get_status_display(),
                container.remarks or "",
            ]
        )
    response = _pdf_report_response(
        "container_returns_report.pdf", "Container Returns Report", headers, rows
    )
    log_audit("container_return", "export", 0, "PDF Export", request.user)
    return response


@login_required
def notifications_mark_all_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return _redirect_back(request, default="dashboard")


@login_required
@director_required
def export_transactions_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        'attachment; filename="trade_transactions_report.csv"'
    )
    writer = csv.writer(response)
    writer.writerow(
        [
            "Entry Number",
            "Client",
            "Status",
            "Description",
            "Estimated Delivery",
            "Created By",
            "Created At",
        ]
    )
    for transaction in Transaction.objects.select_related("customer", "created_by"):
        writer.writerow(
            [
                transaction.transaction_id,
                transaction.customer.name,
                transaction.get_status_display(),
                transaction.description or "",
                (
                    transaction.estimated_delivery.isoformat()
                    if transaction.estimated_delivery
                    else ""
                ),
                transaction.created_by.username,
                _format_datetime(transaction.created_at),
            ]
        )
    log_audit("transaction", "export", 0, "CSV Export", request.user)
    return response


@login_required
@director_required
def export_transactions_pdf(request):
    headers = [
        "Entry Number",
        "Client",
        "Status",
        "Description",
        "Estimated Delivery",
        "Created By",
        "Created At",
    ]
    rows = [
        [
            transaction.transaction_id,
            transaction.customer.name,
            transaction.get_status_display(),
            transaction.description or "",
            (
                transaction.estimated_delivery.isoformat()
                if transaction.estimated_delivery
                else ""
            ),
            transaction.created_by.username,
            _format_datetime(transaction.created_at),
        ]
        for transaction in Transaction.objects.select_related("customer", "created_by")
    ]
    response = _pdf_report_response(
        "trade_transactions_report.pdf", "Trade Transactions Report", headers, rows
    )
    log_audit("transaction", "export", 0, "PDF Export", request.user)
    return response


@login_required
@director_required
def export_sourcing_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="sourcing_report.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Entry Number",
            "Client",
            "Supplier",
            "Supplier Contact",
            "Item Lines",
            "Price Entries",
            "Notes",
            "Created By",
            "Created At",
        ]
    )
    queryset = Sourcing.objects.select_related("transaction__customer", "created_by")
    for sourcing in queryset:
        writer.writerow(
            [
                sourcing.transaction.transaction_id,
                sourcing.transaction.customer.name,
                sourcing.supplier_name,
                sourcing.supplier_contact or "",
                _count_collection(sourcing.item_details),
                _count_collection(sourcing.unit_prices),
                sourcing.notes or "",
                sourcing.created_by.username,
                _format_datetime(sourcing.created_at),
            ]
        )
    log_audit("sourcing", "export", 0, "CSV Export", request.user)
    return response


@login_required
@director_required
def export_sourcing_pdf(request):
    headers = [
        "Entry Number",
        "Client",
        "Supplier",
        "Supplier Contact",
        "Item Lines",
        "Price Entries",
        "Notes",
        "Created By",
        "Created At",
    ]
    rows = [
        [
            sourcing.transaction.transaction_id,
            sourcing.transaction.customer.name,
            sourcing.supplier_name,
            sourcing.supplier_contact or "",
            _count_collection(sourcing.item_details),
            _count_collection(sourcing.unit_prices),
            sourcing.notes or "",
            sourcing.created_by.username,
            _format_datetime(sourcing.created_at),
        ]
        for sourcing in Sourcing.objects.select_related(
            "transaction__customer", "created_by"
        )
    ]
    response = _pdf_report_response(
        "sourcing_report.pdf", "Sourcing Activity Report", headers, rows
    )
    log_audit("sourcing", "export", 0, "PDF Export", request.user)
    return response


@login_required
@director_required
def export_proformas_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        'attachment; filename="proforma_invoices_report.csv"'
    )
    writer = csv.writer(response)
    writer.writerow(
        [
            "Record",
            "Entry Number",
            "Client",
            "Status",
            "Supplier",
            "Item Lines",
            "Subtotal",
            "Validity Date",
            "Created By",
            "Created At",
        ]
    )
    queryset = ProformaInvoice.objects.select_related(
        "transaction__customer", "created_by"
    )
    for proforma in queryset:
        writer.writerow(
            [
                f"PI-{proforma.pk}",
                proforma.transaction.transaction_id,
                proforma.transaction.customer.name,
                proforma.get_status_display(),
                proforma.supplier_name or "",
                _count_collection(proforma.items),
                proforma.subtotal,
                proforma.validity_date.isoformat(),
                proforma.created_by.username,
                _format_datetime(proforma.created_at),
            ]
        )
    log_audit("proforma_invoice", "export", 0, "CSV Export", request.user)
    return response


@login_required
@director_required
def export_proformas_pdf(request):
    headers = [
        "Record",
        "Entry Number",
        "Client",
        "Status",
        "Supplier",
        "Item Lines",
        "Subtotal",
        "Validity Date",
        "Created By",
        "Created At",
    ]
    rows = [
        [
            f"PI-{proforma.pk}",
            proforma.transaction.transaction_id,
            proforma.transaction.customer.name,
            proforma.get_status_display(),
            proforma.supplier_name or "",
            _count_collection(proforma.items),
            f"{proforma.subtotal:,.2f}",
            proforma.validity_date.isoformat(),
            proforma.created_by.username,
            _format_datetime(proforma.created_at),
        ]
        for proforma in ProformaInvoice.objects.select_related(
            "transaction__customer", "created_by"
        )
    ]
    response = _pdf_report_response(
        "proforma_invoices_report.pdf", "Proforma Invoices Report", headers, rows
    )
    log_audit("proforma_invoice", "export", 0, "PDF Export", request.user)
    return response


@login_required
@director_required
def export_final_invoices_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="final_invoices_report.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Record",
            "Entry Number",
            "Client",
            "Confirmed",
            "Shipping Mode",
            "Route",
            "Currency",
            "Total Amount",
            "Confirmed At",
            "Created At",
        ]
    )
    queryset = FinalInvoice.objects.select_related("transaction__customer")
    for invoice in queryset:
        writer.writerow(
            [
                f"FI-{invoice.pk}",
                invoice.transaction.transaction_id,
                invoice.transaction.customer.name,
                "Yes" if invoice.is_confirmed else "No",
                invoice.get_shipping_mode_display(),
                invoice.route,
                invoice.currency,
                invoice.total_amount,
                _format_datetime(invoice.confirmed_at),
                _format_datetime(invoice.created_at),
            ]
        )
    log_audit("final_invoice", "export", 0, "CSV Export", request.user)
    return response


@login_required
@director_required
def export_final_invoices_pdf(request):
    headers = [
        "Record",
        "Entry Number",
        "Client",
        "Confirmed",
        "Shipping Mode",
        "Route",
        "Currency",
        "Total Amount",
        "Confirmed At",
        "Created At",
    ]
    rows = [
        [
            f"FI-{invoice.pk}",
            invoice.transaction.transaction_id,
            invoice.transaction.customer.name,
            "Yes" if invoice.is_confirmed else "No",
            invoice.get_shipping_mode_display(),
            invoice.route,
            invoice.currency,
            f"{invoice.total_amount:,.2f}",
            _format_datetime(invoice.confirmed_at),
            _format_datetime(invoice.created_at),
        ]
        for invoice in FinalInvoice.objects.select_related("transaction__customer")
    ]
    response = _pdf_report_response(
        "final_invoices_report.pdf", "Final Invoices Report", headers, rows
    )
    log_audit("final_invoice", "export", 0, "PDF Export", request.user)
    return response


@login_required
@director_required
def export_purchase_orders_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        'attachment; filename="purchase_orders_report.csv"'
    )
    writer = csv.writer(response)
    writer.writerow(
        [
            "PO Number",
            "Entry Number",
            "Client",
            "Supplier",
            "Status",
            "Item Lines",
            "Subtotal",
            "Linked Invoice",
            "Split PO",
            "Created At",
        ]
    )
    queryset = PurchaseOrder.objects.select_related(
        "transaction__customer", "final_invoice", "parent_po"
    )
    for purchase_order in queryset:
        writer.writerow(
            [
                purchase_order.po_number,
                purchase_order.transaction.transaction_id,
                purchase_order.transaction.customer.name,
                purchase_order.supplier_name,
                purchase_order.get_status_display(),
                _count_collection(purchase_order.items),
                purchase_order.subtotal,
                (
                    f"FI-{purchase_order.final_invoice_id}"
                    if purchase_order.final_invoice_id
                    else ""
                ),
                "Yes" if purchase_order.is_split else "No",
                _format_datetime(purchase_order.created_at),
            ]
        )
    log_audit("purchase_order", "export", 0, "CSV Export", request.user)
    return response


@login_required
@director_required
def export_purchase_orders_pdf(request):
    headers = [
        "PO Number",
        "Entry Number",
        "Client",
        "Supplier",
        "Status",
        "Item Lines",
        "Subtotal",
        "Linked Invoice",
        "Split PO",
        "Created At",
    ]
    rows = [
        [
            purchase_order.po_number,
            purchase_order.transaction.transaction_id,
            purchase_order.transaction.customer.name,
            purchase_order.supplier_name,
            purchase_order.get_status_display(),
            _count_collection(purchase_order.items),
            f"{purchase_order.subtotal:,.2f}",
            (
                f"FI-{purchase_order.final_invoice_id}"
                if purchase_order.final_invoice_id
                else ""
            ),
            "Yes" if purchase_order.is_split else "No",
            _format_datetime(purchase_order.created_at),
        ]
        for purchase_order in PurchaseOrder.objects.select_related(
            "transaction__customer", "final_invoice", "parent_po"
        )
    ]
    response = _pdf_report_response(
        "purchase_orders_report.pdf", "Purchase Orders Report", headers, rows
    )
    log_audit("purchase_order", "export", 0, "PDF Export", request.user)
    return response


@login_required
@director_required
def export_trade_payments_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="trade_payments_report.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Entry Number",
            "Client",
            "Final Invoice",
            "Amount Due Snapshot",
            "Amount Paid",
            "Currency",
            "Balance After",
            "Full Payment",
            "Payment Method",
            "Reference",
            "Payment Date",
            "Created By",
        ]
    )
    queryset = TransactionPaymentRecord.objects.select_related(
        "transaction__customer", "final_invoice", "created_by"
    )
    for record in queryset:
        writer.writerow(
            [
                record.transaction.transaction_id,
                record.transaction.customer.name,
                f"FI-{record.final_invoice_id}" if record.final_invoice_id else "",
                record.amount_due_snapshot,
                record.amount,
                record.currency,
                record.balance_after,
                "Yes" if record.is_full_payment else "No",
                record.get_payment_method_display(),
                record.reference or "",
                _format_datetime(record.payment_date),
                record.created_by.username,
            ]
        )
    log_audit("transaction_payment_record", "export", 0, "CSV Export", request.user)
    return response


@login_required
@director_required
def export_trade_payments_pdf(request):
    headers = [
        "Entry Number",
        "Client",
        "Final Invoice",
        "Amount Due",
        "Amount Paid",
        "Currency",
        "Balance After",
        "Full Payment",
        "Method",
        "Reference",
        "Payment Date",
        "Created By",
    ]
    rows = [
        [
            record.transaction.transaction_id,
            record.transaction.customer.name,
            f"FI-{record.final_invoice_id}" if record.final_invoice_id else "",
            f"{record.amount_due_snapshot:,.2f}",
            f"{record.amount:,.2f}",
            record.currency,
            f"{record.balance_after:,.2f}",
            "Yes" if record.is_full_payment else "No",
            record.get_payment_method_display(),
            record.reference or "",
            _format_datetime(record.payment_date),
            record.created_by.username,
        ]
        for record in TransactionPaymentRecord.objects.select_related(
            "transaction__customer", "final_invoice", "created_by"
        )
    ]
    response = _pdf_report_response(
        "trade_payments_report.pdf", "Trade Payments Report", headers, rows
    )
    log_audit("transaction_payment_record", "export", 0, "PDF Export", request.user)
    return response


# ===== AUDIT LOGS =====


@login_required
def audit_log_view(request):
    if request.user.role not in {"ADMIN", "superuser"}:
        messages.error(request, "Permission denied")
        return redirect("dashboard")
    logs = AuditLog.objects.select_related("user")
    total_logs = logs.count()
    page_obj, query_string, page_range = paginate_queryset(
        request, logs, per_page=AUDIT_PAGE_SIZE
    )
    return render(
        request,
        "logistics/audit_logs.html",
        {
            "logs": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "page_range": page_range,
            "total_logs": total_logs,
        },
    )


@login_required
def workflow_guide(request):
    """Static workflow reference page — accessible to all authenticated users."""
    if request.GET.get("download") == "1":
        from django.template.loader import render_to_string

        html = render_to_string(
            "logistics/workflow_guide.html",
            {"download_mode": True, "request": request, "user": request.user},
        )
        response = HttpResponse(html, content_type="text/html; charset=utf-8")
        response["Content-Disposition"] = (
            'attachment; filename="GMI_Terralink_Workflow_Guide.html"'
        )
        return response
    return render(request, "logistics/workflow_guide.html")


# ===== UTILITIES =====


def paginate_queryset(request, queryset, per_page=DEFAULT_PAGE_SIZE):
    """Paginate any queryset while preserving existing filters/searches."""
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    query_params = request.GET.copy()
    if "page" in query_params:
        query_params.pop("page")
    query_string = query_params.urlencode()
    if query_string:
        query_string = f"{query_string}&"
    page_range = paginator.get_elided_page_range(page_obj.number)
    return page_obj, query_string, page_range


def log_audit(model_type, action, object_id, object_str, user):
    AuditLog.objects.create(
        user=user,
        model_type=model_type,
        action=action,
        object_id=object_id,
        object_str=object_str,
    )


@login_required
@director_required
def director_finance_summary(request):
    """Director-only reporting endpoint for revenue, balances, status counts and trends."""
    conversion = DirectorReportingService.conversion_rate()
    top_clients = DirectorReportingService.top_clients()
    payload = {
        "total_revenue": float(DirectorReportingService.total_revenue() or 0),
        "outstanding_balances": float(
            DirectorReportingService.outstanding_balances() or 0
        ),
        "active_shipments": DirectorReportingService.active_shipments_count(),
        "conversion_rate": conversion,
        "top_clients": top_clients,
        "profit_estimate": float(DirectorReportingService.profit_estimate() or 0),
        "transactions_per_status": DirectorReportingService.transactions_per_status(),
        "revenue_trends": DirectorReportingService.revenue_trends(),
    }
    return JsonResponse(payload)


# ===== RECEIPTS =====


@login_required
def receipt_list(request):
    """List all system-generated receipts."""
    receipts = Receipt.objects.select_related(
        "logistics_payment__payment__loading__client",
        "sourcing_payment__transaction__customer",
    ).all()

    source_filter = (request.GET.get("source") or "all").strip().lower()
    if source_filter == "logistics":
        receipts = receipts.filter(logistics_payment__isnull=False)
    elif source_filter == "sourcing":
        receipts = receipts.filter(sourcing_payment__isnull=False)

    payment_filter = (request.GET.get("payment_filter") or "all").strip().lower()
    if payment_filter == "full":
        receipts = receipts.filter(
            sourcing_payment__isnull=False,
            sourcing_payment__is_full_payment=True,
        )
    elif payment_filter == "partial":
        receipts = receipts.filter(
            sourcing_payment__isnull=False,
            sourcing_payment__is_full_payment=False,
        )

    search = request.GET.get("search", "")
    if search:
        receipts = receipts.filter(
            Q(receipt_number__icontains=search) | Q(issued_to__icontains=search)
        )
    page_obj, query_string, page_range = paginate_queryset(request, receipts)
    return render(
        request,
        "logistics/receipts/list.html",
        {
            "receipts": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "page_range": page_range,
            "search": search,
            "payment_filter": payment_filter,
            "source_filter": source_filter,
        },
    )


@login_required
def receipt_detail(request, pk):
    """View a single receipt."""
    receipt = get_object_or_404(Receipt, pk=pk)
    can_reverse_receipt = (
        request.user.is_superuser or getattr(request.user, "role", "") == "DIRECTOR"
    )
    return render(
        request,
        "logistics/receipts/detail.html",
        {"receipt": receipt, "can_reverse_receipt": can_reverse_receipt},
    )


@login_required
def receipt_pdf(request, pk):
    """Download a receipt as PDF."""
    receipt = get_object_or_404(Receipt, pk=pk)
    pdf_bytes = receipt.generate_pdf()
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="Receipt-{receipt.receipt_number}.pdf"'
    )
    return response


@login_required
def receipt_reverse(request, pk):
    """Mark a receipt as reversed/refunded by an authorised user. Does not delete the record."""
    receipt = get_object_or_404(Receipt, pk=pk)
    can_reverse_receipt = (
        request.user.is_superuser or getattr(request.user, "role", "") == "DIRECTOR"
    )
    if not can_reverse_receipt:
        messages.error(
            request,
            "Director authorization is required to reverse or refund a receipt.",
        )
        return redirect("receipt_detail", pk=pk)
    if receipt.is_reversed:
        messages.warning(request, "This receipt has already been reversed.")
        return redirect("receipt_detail", pk=pk)
    if request.method == "POST":
        notes = request.POST.get("reversal_notes", "").strip()
        receipt.is_reversed = True
        receipt.reversed_at = timezone.now()
        receipt.reversed_by = request.user
        receipt.reversal_notes = notes
        receipt.save()
        messages.success(
            request, f"Receipt {receipt.receipt_number} has been reversed."
        )
        return redirect("receipt_list")
    return render(request, "logistics/receipts/reverse.html", {"receipt": receipt})


# ===== SOURCING PAYMENTS =====


@login_required
@finance_required
def sourcing_payment_create(request, transaction_pk=None):
    """Record a payment against a sourcing Transaction."""
    initial = {}
    requested_mode = (request.GET.get("mode") or "").strip().lower()
    if requested_mode == "full":
        initial["is_full_payment"] = True
    elif requested_mode == "partial":
        initial["is_full_payment"] = False

    txn = None
    fi = None
    if transaction_pk:
        txn = get_object_or_404(Transaction, pk=transaction_pk)
        initial["transaction"] = txn
        # Pre-select the latest FinalInvoice (confirmed first, else any)
        fi = (
            FinalInvoice.objects.filter(transaction=txn)
            .order_by("-is_confirmed", "-created_at")
            .first()
        )
        if fi:
            initial["final_invoice"] = fi
            total_paid = (
                txn.payment_records.aggregate(total=Sum("amount"))["total"] or 0
            )
            amount_due = max(fi.total_amount - total_paid, 0)
            initial["currency"] = fi.currency
            initial["amount_due_snapshot"] = amount_due
            initial["balance_after"] = amount_due
            initial["change_given"] = 0

    if request.method == "POST":
        form = TransactionPaymentRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.created_by = request.user
            record.save()
            transaction = record.transaction
            po_message = None
            invoice = (
                record.final_invoice
                or transaction.final_invoices.order_by("-created_at").first()
            )
            if invoice:
                total_paid = (
                    transaction.payment_records.aggregate(total=Sum("amount"))["total"]
                    or 0
                )
                if total_paid >= invoice.total_amount:
                    Transaction.objects.filter(pk=transaction.pk).update(status="PAID")
                    purchase_order, created = _ensure_purchase_order_for_transaction(
                        transaction,
                        request.user,
                        invoice=invoice,
                    )
                    if created and purchase_order:
                        po_message = (
                            f" Purchase Order {purchase_order.po_number} generated."
                        )
                        _notify_roles(
                            title="Purchase order generated",
                            message=f"PO {purchase_order.po_number} created for {transaction.transaction_id}.",
                            link=f"/invoicing/purchase-orders/{purchase_order.pk}/",
                            category="trading",
                            roles=["ADMIN", "DIRECTOR", "FINANCE", "PROCUREMENT"],
                        )
            _notify_roles(
                title="Client payment received",
                message=(
                    f"{record.amount} {record.currency} received for "
                    f"{transaction.transaction_id}."
                ),
                link=f"/transactions/{transaction.pk}/",
                category="trading",
                roles=["ADMIN", "DIRECTOR", "FINANCE", "PROCUREMENT"],
            )
            messages.success(
                request,
                f"Payment recorded. Receipt {record.receipt.receipt_number} generated.{po_message or ''}",
            )
            return redirect("receipt_list")
    else:
        form = TransactionPaymentRecordForm(initial=initial)

    selected_txn = None
    selected_invoice = None
    amount_due = None
    total_paid = None
    if form.is_bound:
        selected_txn = form.cleaned_data.get("transaction") if form.is_valid() else None
    elif txn:
        selected_txn = txn
        selected_invoice = fi

    if selected_txn and not selected_invoice:
        selected_invoice = selected_txn.final_invoices.order_by(
            "-is_confirmed", "-created_at"
        ).first()
    if selected_txn and selected_invoice:
        total_paid = (
            selected_txn.payment_records.aggregate(total=Sum("amount"))["total"] or 0
        )
        amount_due = max(selected_invoice.total_amount - total_paid, 0)

    return render(
        request,
        "logistics/sourcing_payments/form.html",
        {
            "form": form,
            "title": "Record Trade Payment",
            "selected_transaction": selected_txn,
            "selected_invoice": selected_invoice,
            "amount_due": amount_due,
            "total_paid": total_paid,
            "due_info_url": reverse("sourcing_payment_due_info"),
        },
    )


@login_required
@finance_required
def sourcing_payment_due_info(request):
    """Return invoice due/paid amounts for the selected sourcing transaction."""
    transaction_id = request.GET.get("transaction_id")
    invoice_id = request.GET.get("invoice_id")

    if not transaction_id:
        return JsonResponse(
            {"ok": False, "message": "transaction_id is required."}, status=400
        )

    try:
        transaction_id = int(transaction_id)
    except (TypeError, ValueError):
        return JsonResponse(
            {"ok": False, "message": "transaction_id must be a valid integer."},
            status=400,
        )

    transaction = get_object_or_404(Transaction, pk=transaction_id)
    invoice_queryset = FinalInvoice.objects.filter(
        transaction=transaction,
    ).order_by("-is_confirmed", "-created_at")

    selected_invoice = None
    if invoice_id:
        try:
            invoice_id = int(invoice_id)
        except (TypeError, ValueError):
            return JsonResponse(
                {"ok": False, "message": "invoice_id must be a valid integer."},
                status=400,
            )
        selected_invoice = invoice_queryset.filter(pk=invoice_id).first()
        if not selected_invoice:
            # Fallback gracefully to the latest invoice for the chosen transaction.
            selected_invoice = invoice_queryset.first()
    else:
        selected_invoice = invoice_queryset.first()

    total_paid = (
        transaction.payment_records.aggregate(total=Sum("amount"))["total"] or 0
    )

    if not selected_invoice:
        return JsonResponse(
            {
                "ok": False,
                "message": "No confirmed invoice found for this transaction.",
                "invoice_id": None,
                "currency": "USD",
                "total_paid": f"{total_paid:.2f}",
                "amount_due": "0.00",
            }
        )

    amount_due = max(selected_invoice.total_amount - total_paid, 0)
    return JsonResponse(
        {
            "ok": True,
            "invoice_id": selected_invoice.pk,
            "currency": selected_invoice.currency,
            "total_paid": f"{total_paid:.2f}",
            "amount_due": f"{amount_due:.2f}",
        }
    )


@login_required
def sourcing_payment_list(request, transaction_pk):
    """List all payment records for a given Transaction."""
    txn = get_object_or_404(Transaction, pk=transaction_pk)
    records = txn.payment_records.select_related("final_invoice", "created_by").all()
    return render(
        request,
        "logistics/sourcing_payments/list.html",
        {"transaction": txn, "records": records},
    )


# ===== Commission Module =====


def _can_view_commissions(user):
    return user.is_superuser or getattr(user, "role", "") in {"DIRECTOR", "ADMIN"}


@login_required
@director_required
def commission_list(request):
    from .models import Commission

    commissions = Commission.objects.select_related("client", "created_by").all()

    client_id = request.GET.get("client")
    currency = request.GET.get("currency")
    if client_id:
        commissions = commissions.filter(client_id=client_id)
    if currency:
        commissions = commissions.filter(currency=currency)

    totals = (
        commissions.values("currency")
        .annotate(total=Sum("amount"), entries=Count("id"))
        .order_by("currency")
    )

    paginator = Paginator(commissions, DEFAULT_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "logistics/commissions/list.html",
        {
            "commissions": page_obj,
            "page_obj": page_obj,
            "totals": list(totals),
            "clients": Client.objects.order_by("name"),
            "filter_client": client_id or "",
            "filter_currency": currency or "",
        },
    )


@login_required
@director_required
def commission_create(request):
    from .forms import CommissionForm

    if request.method == "POST":
        form = CommissionForm(request.POST)
        if form.is_valid():
            commission = form.save(commit=False)
            commission.created_by = request.user
            commission.save()
            messages.success(request, "Commission entry recorded successfully.")
            log_audit(
                "commission",
                "create",
                commission.id,
                str(commission),
                request.user,
            )
            return redirect("commission_list")
    else:
        form = CommissionForm()
    return render(
        request,
        "logistics/commissions/form.html",
        {"form": form, "title": "Record Commission"},
    )


@login_required
@director_required
def commission_update(request, pk):
    from .forms import CommissionForm
    from .models import Commission

    commission = get_object_or_404(Commission, pk=pk)
    if request.method == "POST":
        form = CommissionForm(request.POST, instance=commission)
        if form.is_valid():
            form.save()
            messages.success(request, "Commission entry updated.")
            log_audit(
                "commission",
                "update",
                commission.id,
                str(commission),
                request.user,
            )
            return redirect("commission_list")
    else:
        form = CommissionForm(instance=commission)
    return render(
        request,
        "logistics/commissions/form.html",
        {"form": form, "title": "Update Commission", "commission": commission},
    )


@login_required
@director_required
def commission_delete(request, pk):
    from .models import Commission

    commission = get_object_or_404(Commission, pk=pk)
    if request.method == "POST":
        label = str(commission)
        commission_id = commission.id
        commission.delete()
        log_audit("commission", "delete", commission_id, label, request.user)
        messages.success(request, "Commission entry deleted.")
        return redirect("commission_list")
    return render(
        request,
        "logistics/commissions/confirm_delete.html",
        {"commission": commission},
    )


# ---------------------------------------------------------------------------
# Proof of Delivery (shared between Logistics and Sourcing/Trading lanes)
# ---------------------------------------------------------------------------


def _render_pod_form(request, *, target, side, form):
    """Render the POD capture form for either lane."""
    return render(
        request,
        "logistics/pod/form.html",
        {
            "form": form,
            "target": target,
            "side": side,
            "is_logistics": side == "logistics",
            "is_trading": side == "trading",
        },
    )


@login_required
@role_required("ADMIN", "DIRECTOR", "FINANCE", "OFFICE_ADMIN")
def record_logistics_pod(request, loading_pk):
    """Capture POD for a Loading (logistics lane)."""
    loading = get_object_or_404(Loading, pk=loading_pk)
    if hasattr(loading, "proof_of_delivery"):
        messages.info(
            request,
            f"Proof of Delivery {loading.proof_of_delivery.pod_number} already exists for this loading.",
        )
        return redirect("pod_detail", pk=loading.proof_of_delivery.pk)

    if request.method == "POST":
        form = ProofOfDeliveryForm(request.POST, request.FILES)
        if form.is_valid():
            pod = form.save(commit=False)
            pod.loading = loading
            pod.created_by = request.user
            pod.save()
            messages.success(
                request,
                f"Proof of Delivery {pod.pod_number} recorded for loading {loading.loading_id}.",
            )
            _notify_roles(
                title="Proof of Delivery captured",
                message=f"POD {pod.pod_number} recorded for loading {loading.loading_id}.",
                link=f"/pod/{pod.pk}/",
                category="logistics",
                roles=["ADMIN", "DIRECTOR", "FINANCE", "OFFICE_ADMIN"],
            )
            return redirect("pod_detail", pk=pod.pk)
    else:
        form = ProofOfDeliveryForm(initial={"delivered_at": timezone.now()})

    return _render_pod_form(request, target=loading, side="logistics", form=form)


@login_required
@role_required("ADMIN", "DIRECTOR", "FINANCE", "PROCUREMENT")
def record_trading_pod(request, fulfillment_pk):
    """Capture POD for a FulfillmentOrder (sourcing / trading lane)."""
    fulfillment = get_object_or_404(FulfillmentOrder, pk=fulfillment_pk)
    if hasattr(fulfillment, "proof_of_delivery"):
        messages.info(
            request,
            f"Proof of Delivery {fulfillment.proof_of_delivery.pod_number} already exists for this fulfillment.",
        )
        return redirect("pod_detail", pk=fulfillment.proof_of_delivery.pk)

    if request.method == "POST":
        form = ProofOfDeliveryForm(request.POST, request.FILES)
        if form.is_valid():
            pod = form.save(commit=False)
            pod.fulfillment_order = fulfillment
            pod.created_by = request.user
            pod.save()
            messages.success(
                request,
                f"Proof of Delivery {pod.pod_number} recorded for fulfillment {fulfillment.fulfillment_id}.",
            )
            _notify_roles(
                title="Proof of Delivery captured",
                message=(
                    f"POD {pod.pod_number} recorded for fulfillment "
                    f"{fulfillment.fulfillment_id} (txn {fulfillment.transaction.transaction_id})."
                ),
                link=f"/pod/{pod.pk}/",
                category="trading",
                roles=["ADMIN", "DIRECTOR", "FINANCE", "PROCUREMENT"],
            )
            return redirect("pod_detail", pk=pod.pk)
    else:
        form = ProofOfDeliveryForm(initial={"delivered_at": timezone.now()})

    return _render_pod_form(request, target=fulfillment, side="trading", form=form)


@login_required
def pod_detail(request, pk):
    pod = get_object_or_404(
        ProofOfDelivery.objects.select_related(
            "loading", "fulfillment_order__transaction__customer", "created_by"
        ),
        pk=pk,
    )
    return render(
        request,
        "logistics/pod/detail.html",
        {
            "pod": pod,
            "is_logistics": pod.business_side == "logistics",
            "is_trading": pod.business_side == "trading",
        },
    )


@login_required
def pod_delivery_note_pdf(request, pk):
    pod = get_object_or_404(
        ProofOfDelivery.objects.select_related(
            "loading__client",
            "fulfillment_order__transaction__customer",
            "created_by",
        ),
        pk=pk,
    )
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f"attachment; filename=delivery_note_{pod.pod_number}.pdf"
    )
    pdf = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    _draw_standard_doc_header(pdf, width, height, "DELIVERY NOTE", pod.pod_number)

    y = height - 170
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "Lane:")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(150, y, pod.business_side.title())
    y -= 18

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "Reference:")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(150, y, pod.target_reference or "-")
    y -= 18

    if pod.business_side == "logistics" and pod.loading and pod.loading.client:
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, "Client:")
        pdf.setFont("Helvetica", 11)
        pdf.drawString(150, y, pod.loading.client.name)
        y -= 18
    elif pod.business_side == "trading" and pod.fulfillment_order:
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, "Customer:")
        pdf.setFont("Helvetica", 11)
        pdf.drawString(150, y, pod.fulfillment_order.transaction.customer.name)
        y -= 18

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "Delivered at:")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(150, y, pod.delivered_at.strftime("%Y-%m-%d %H:%M"))
    y -= 18

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "Received by:")
    pdf.setFont("Helvetica", 11)
    received = pod.received_by_name + (
        f"  ({pod.received_by_phone})" if pod.received_by_phone else ""
    )
    pdf.drawString(150, y, received)
    y -= 18

    if pod.delivery_address:
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, "Address:")
        pdf.setFont("Helvetica", 11)
        pdf.drawString(150, y, pod.delivery_address[:80])
        y -= 18

    if pod.gps_lat is not None and pod.gps_lng is not None:
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, "GPS:")
        pdf.setFont("Helvetica", 11)
        pdf.drawString(150, y, f"{pod.gps_lat}, {pod.gps_lng}")
        y -= 18

    if pod.notes:
        y -= 10
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, "Notes:")
        y -= 16
        pdf.setFont("Helvetica", 10)
        for chunk in [pod.notes[i : i + 95] for i in range(0, len(pod.notes), 95)][:8]:
            pdf.drawString(50, y, chunk)
            y -= 14

    y -= 30
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "Receiver Signature:")
    pdf.line(180, y - 2, 420, y - 2)
    y -= 30
    pdf.drawString(50, y, "Issued by:")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(150, y, pod.created_by.get_full_name() or pod.created_by.username)

    _draw_international_terms_footer(pdf, 50, 110)
    pdf.showPage()
    pdf.save()
    return response


# ---------------------------------------------------------------------------
# Tracking timelines (logistics Transit + trading Fulfillment ShipmentLegs)
# ---------------------------------------------------------------------------


def _build_transit_milestones(transit):
    """Return a list of milestone dicts for the logistics transit timeline."""
    loading = transit.loading
    pod = getattr(loading, "proof_of_delivery", None)
    now = timezone.now()
    milestones = []

    milestones.append(
        {
            "label": "Cargo registered",
            "icon": "bi-box-seam-fill",
            "state": "done",
            "timestamp": loading.loading_date,
            "detail": f"Loading {loading.loading_id} - {loading.client.name}",
        }
    )

    boarding_state = (
        "done" if transit.boarding_date and transit.boarding_date <= now else "pending"
    )
    milestones.append(
        {
            "label": "Boarding / Departure",
            "icon": "bi-truck-flatbed",
            "state": boarding_state,
            "timestamp": transit.boarding_date,
            "detail": f"Vessel {transit.vessel_name}",
        }
    )

    in_transit_state = (
        "done" if transit.status in ("in_transit", "arrived") else "pending"
    )
    milestones.append(
        {
            "label": "In transit",
            "icon": "bi-compass-fill",
            "state": in_transit_state,
            "timestamp": transit.boarding_date,
            "detail": transit.remarks or "",
        }
    )

    eta_late = (
        transit.status != "arrived"
        and transit.eta_kampala
        and transit.eta_kampala < now
    )
    eta_state = (
        "done" if transit.status == "arrived" else ("late" if eta_late else "pending")
    )
    milestones.append(
        {
            "label": "ETA Kampala",
            "icon": "bi-flag-fill",
            "state": eta_state,
            "timestamp": transit.eta_kampala,
            "detail": "Estimated arrival",
        }
    )

    arrived_state = "done" if transit.status == "arrived" else "pending"
    milestones.append(
        {
            "label": "Arrived",
            "icon": "bi-geo-alt-fill",
            "state": arrived_state,
            "timestamp": transit.updated_at if transit.status == "arrived" else None,
            "detail": "",
        }
    )

    pod_state = "done" if pod else "pending"
    milestones.append(
        {
            "label": "Proof of Delivery",
            "icon": "bi-file-earmark-check",
            "state": pod_state,
            "timestamp": pod.delivered_at if pod else None,
            "detail": (
                f"POD {pod.pod_number} - received by {pod.received_by_name}"
                if pod
                else "Not captured yet"
            ),
            "link": f"/pod/{pod.pk}/" if pod else None,
        }
    )

    return milestones


@login_required
def transit_detail(request, pk):
    """Read-only timeline view for a single Transit (logistics lane)."""
    transit = get_object_or_404(
        Transit.objects.select_related("loading__client", "created_by"), pk=pk
    )
    milestones = _build_transit_milestones(transit)
    return render(
        request,
        "logistics/transits/detail.html",
        {
            "transit": transit,
            "loading": transit.loading,
            "milestones": milestones,
            "pod": getattr(transit.loading, "proof_of_delivery", None),
            "tracking_token": make_tracking_token("transit", transit.pk),
        },
    )


def _build_fulfillment_milestones(fulfillment):
    """Return milestones for the trading fulfillment timeline (order + legs + POD)."""
    pod = getattr(fulfillment, "proof_of_delivery", None)
    now = timezone.now().date()
    milestones = []

    milestones.append(
        {
            "label": "Fulfillment opened",
            "icon": "bi-diagram-3-fill",
            "state": "done",
            "timestamp": fulfillment.created_at,
            "detail": f"Status: {fulfillment.get_status_display()}",
        }
    )

    legs = list(fulfillment.legs.all().order_by("sequence", "created_at"))
    for leg in legs:
        is_late = (
            leg.status not in ("ARRIVED", "COMPLETED")
            and leg.arrival_eta
            and leg.arrival_eta < now
        )
        if leg.status in ("ARRIVED", "COMPLETED"):
            state = "done"
        elif is_late:
            state = "late"
        elif leg.status == "IN_TRANSIT":
            state = "active"
        else:
            state = "pending"
        milestones.append(
            {
                "label": f"Leg {leg.sequence}: {leg.get_leg_type_display()}",
                "icon": "bi-signpost-split-fill",
                "state": state,
                "timestamp": leg.actual_arrival
                or leg.arrival_eta
                or leg.departure_date,
                "detail": (
                    f"{leg.origin} -> {leg.destination}"
                    + (f" via {leg.carrier}" if leg.carrier else "")
                    + f" - {leg.get_status_display()}"
                ),
            }
        )

    pod_state = "done" if pod else "pending"
    milestones.append(
        {
            "label": "Proof of Delivery",
            "icon": "bi-file-earmark-check",
            "state": pod_state,
            "timestamp": pod.delivered_at if pod else None,
            "detail": (
                f"POD {pod.pod_number} - received by {pod.received_by_name}"
                if pod
                else "Not captured yet"
            ),
            "link": f"/pod/{pod.pk}/" if pod else None,
        }
    )

    return milestones


@login_required
def fulfillment_timeline(request, pk):
    """Read-only timeline view for a FulfillmentOrder (sourcing / trading lane)."""
    fulfillment = get_object_or_404(
        FulfillmentOrder.objects.select_related(
            "transaction__customer"
        ).prefetch_related("legs"),
        pk=pk,
    )
    milestones = _build_fulfillment_milestones(fulfillment)
    return render(
        request,
        "logistics/fulfillment/timeline.html",
        {
            "fulfillment": fulfillment,
            "transaction": fulfillment.transaction,
            "milestones": milestones,
            "pod": getattr(fulfillment, "proof_of_delivery", None),
            "tracking_token": make_tracking_token("fulfillment", fulfillment.pk),
        },
    )


# ---------------------------------------------------------------------------
# Public tracking link (signed token) + POD list
# ---------------------------------------------------------------------------

from django.core import signing as _tracking_signing  # noqa: E402

_TRACKING_SALT = "gmi.public.tracking"
_TRACKING_MAX_AGE = 60 * 60 * 24 * 90  # 90 days


def make_tracking_token(kind, pk):
    """Return a signed, URL-safe token for ``kind`` (``transit``/``fulfillment``) and ``pk``."""
    return _tracking_signing.dumps({"k": kind, "p": int(pk)}, salt=_TRACKING_SALT)


def _decode_tracking_token(token):
    try:
        return _tracking_signing.loads(
            token, salt=_TRACKING_SALT, max_age=_TRACKING_MAX_AGE
        )
    except _tracking_signing.SignatureExpired:
        return {"_error": "expired"}
    except _tracking_signing.BadSignature:
        return {"_error": "invalid"}


def public_track(request, token):
    """Read-only public tracking page reachable by anyone with a signed link."""
    payload = _decode_tracking_token(token)
    if "_error" in payload:
        return render(
            request,
            "logistics/tracking/public.html",
            {"error": payload["_error"]},
            status=404,
        )

    kind = payload.get("k")
    pk = payload.get("p")
    if kind == "transit":
        transit = get_object_or_404(
            Transit.objects.select_related("loading__client"), pk=pk
        )
        milestones = _build_transit_milestones(transit)
        ctx = {
            "kind": "transit",
            "title": f"Shipment {transit.loading.loading_id}",
            "subtitle": f"Vessel {transit.vessel_name}",
            "client": transit.loading.client.name,
            "status_label": transit.get_status_display(),
            "milestones": milestones,
            "eta": transit.eta_kampala,
        }
    elif kind == "fulfillment":
        fulfillment = get_object_or_404(
            FulfillmentOrder.objects.select_related(
                "transaction__customer"
            ).prefetch_related("legs"),
            pk=pk,
        )
        milestones = _build_fulfillment_milestones(fulfillment)
        ctx = {
            "kind": "fulfillment",
            "title": f"Order #{fulfillment.id}",
            "subtitle": fulfillment.transaction.transaction_id,
            "client": fulfillment.transaction.customer.name,
            "status_label": fulfillment.get_status_display(),
            "milestones": milestones,
            "eta": fulfillment.planned_delivery_date,
        }
    else:
        return render(
            request,
            "logistics/tracking/public.html",
            {"error": "invalid"},
            status=404,
        )

    return render(request, "logistics/tracking/public.html", ctx)


@login_required
def pod_list(request):
    """List proof-of-delivery records, filterable by lane via ?lane=logistics|trading."""
    lane = (request.GET.get("lane") or "").lower()
    qs = ProofOfDelivery.objects.select_related(
        "loading__client",
        "fulfillment_order__transaction__customer",
        "created_by",
    ).order_by("-delivered_at")
    if lane == "logistics":
        qs = qs.filter(loading__isnull=False)
    elif lane == "trading":
        qs = qs.filter(fulfillment_order__isnull=False)
    return render(
        request,
        "logistics/pod/list.html",
        {"pods": qs, "lane": lane},
    )


# ---------------------------------------------------------------------------
# Phase D: Trade / Loading closure
# ---------------------------------------------------------------------------


def _closure_item(label, ok, detail=""):
    return {"label": label, "ok": bool(ok), "detail": detail}


def evaluate_transaction_closure(transaction):
    """Return (items, ready) for closing a trading transaction."""
    items = []

    proforma = transaction.proforma_invoices.order_by("-created_at").first()
    items.append(
        _closure_item(
            "Proforma invoice issued",
            proforma is not None,
            proforma.proforma_number if proforma else "No proforma yet",
        )
    )

    final_invoice = transaction.final_invoices.order_by("-created_at").first()
    items.append(
        _closure_item(
            "Final invoice issued",
            final_invoice is not None,
            final_invoice.invoice_number if final_invoice else "No final invoice",
        )
    )

    total_paid = (
        transaction.payment_records.aggregate(total=Sum("amount"))["total"] or 0
    )
    invoice_total = final_invoice.total_amount if final_invoice else 0
    paid_ok = bool(final_invoice) and total_paid >= invoice_total and invoice_total > 0
    items.append(
        _closure_item(
            "Customer payment settled",
            paid_ok,
            f"Paid {total_paid} / {invoice_total}",
        )
    )

    fulfillment = getattr(transaction, "fulfillment_order", None)
    delivered = bool(fulfillment) and fulfillment.status == "DELIVERED"
    items.append(
        _closure_item(
            "Fulfillment delivered",
            delivered,
            fulfillment.get_status_display() if fulfillment else "No fulfillment",
        )
    )

    pod = getattr(fulfillment, "proof_of_delivery", None) if fulfillment else None
    items.append(
        _closure_item(
            "Proof of Delivery captured",
            pod is not None,
            pod.pod_number if pod else "Not captured",
        )
    )

    ready = all(item["ok"] for item in items) and not transaction.is_closed
    return items, ready


def evaluate_loading_closure(loading):
    """Return (items, ready) for closing a logistics loading."""
    items = []

    invoice = (
        loading.final_invoices.order_by("-created_at").first()
        if hasattr(loading, "final_invoices")
        else None
    )
    if invoice is None:
        invoice = (
            FinalInvoice.objects.filter(loading=loading).order_by("-created_at").first()
        )
    items.append(
        _closure_item(
            "Freight invoice issued",
            invoice is not None,
            invoice.invoice_number if invoice else "No invoice",
        )
    )

    payments = Payment.objects.filter(loading=loading)
    total_paid = payments.aggregate(total=Sum("amount"))["total"] or 0
    invoice_total = invoice.total_amount if invoice else 0
    paid_ok = bool(invoice) and total_paid >= invoice_total and invoice_total > 0
    items.append(
        _closure_item(
            "Freight payment settled",
            paid_ok,
            f"Paid {total_paid} / {invoice_total}",
        )
    )

    transit = getattr(loading, "transit", None)
    arrived = bool(transit) and transit.status == "arrived"
    items.append(
        _closure_item(
            "Transit arrived",
            arrived,
            transit.get_status_display() if transit else "No transit record",
        )
    )

    pod = getattr(loading, "proof_of_delivery", None)
    items.append(
        _closure_item(
            "Proof of Delivery captured",
            pod is not None,
            pod.pod_number if pod else "Not captured",
        )
    )

    if loading.entry_type == "FULL_CONTAINER":
        container_returned = ContainerReturn.objects.filter(loading=loading).exists()
        items.append(
            _closure_item(
                "Container returned",
                container_returned,
                "Recorded" if container_returned else "Pending",
            )
        )

    ready = all(item["ok"] for item in items) and not loading.is_closed
    return items, ready


@login_required
@role_required("ADMIN", "DIRECTOR", "FINANCE")
def close_transaction(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk)
    if transaction.is_closed:
        messages.info(request, "Transaction already closed.")
        return redirect("transaction_detail", pk=pk)
    items, ready = evaluate_transaction_closure(transaction)
    if not ready:
        missing = [i["label"] for i in items if not i["ok"]]
        messages.error(
            request,
            "Cannot close transaction. Pending: " + ", ".join(missing),
        )
        return redirect("transaction_detail", pk=pk)
    if request.method == "POST":
        transaction.status = "CLOSED"
        transaction.closed_at = timezone.now()
        transaction.closed_by = request.user
        transaction.closure_notes = request.POST.get("closure_notes", "").strip()
        transaction.save()
        messages.success(request, f"Transaction {transaction.transaction_id} closed.")
        _notify_roles(
            title="Trade transaction closed",
            message=(
                f"{transaction.transaction_id} was closed by {request.user.get_full_name() or request.user.username}."
            ),
            link=f"/transactions/{transaction.pk}/",
            category="trading",
            roles=["ADMIN", "DIRECTOR", "FINANCE"],
        )
    return redirect("transaction_detail", pk=pk)


@login_required
@role_required("ADMIN", "DIRECTOR")
def reopen_transaction(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk)
    if not transaction.is_closed:
        messages.info(request, "Transaction is not closed.")
        return redirect("transaction_detail", pk=pk)
    if request.method == "POST":
        transaction.status = "DELIVERED"
        transaction.closed_at = None
        transaction.closed_by = None
        transaction.save()
        messages.success(request, "Transaction reopened.")
    return redirect("transaction_detail", pk=pk)


@login_required
@role_required("ADMIN", "DIRECTOR", "FINANCE", "OFFICE_ADMIN")
def close_loading(request, pk):
    loading = get_object_or_404(Loading, pk=pk)
    if loading.is_closed:
        messages.info(request, "Loading already closed.")
        return redirect("loading_detail", pk=pk)
    items, ready = evaluate_loading_closure(loading)
    if not ready:
        missing = [i["label"] for i in items if not i["ok"]]
        messages.error(
            request,
            "Cannot close loading. Pending: " + ", ".join(missing),
        )
        return redirect("loading_detail", pk=pk)
    if request.method == "POST":
        loading.closed_at = timezone.now()
        loading.closed_by = request.user
        loading.closure_notes = request.POST.get("closure_notes", "").strip()
        loading.save()
        messages.success(request, f"Loading {loading.loading_id} closed.")
        _notify_roles(
            title="Loading closed",
            message=(
                f"{loading.loading_id} was closed by {request.user.get_full_name() or request.user.username}."
            ),
            link=f"/loadings/{loading.pk}/",
            category="logistics",
            roles=["ADMIN", "DIRECTOR", "FINANCE", "OFFICE_ADMIN"],
        )
    return redirect("loading_detail", pk=pk)


@login_required
@role_required("ADMIN", "DIRECTOR")
def reopen_loading(request, pk):
    loading = get_object_or_404(Loading, pk=pk)
    if not loading.is_closed:
        messages.info(request, "Loading is not closed.")
        return redirect("loading_detail", pk=pk)
    if request.method == "POST":
        loading.closed_at = None
        loading.closed_by = None
        loading.save()
        messages.success(request, "Loading reopened.")
    return redirect("loading_detail", pk=pk)


# ===========================================================================
# Phase E: Supplier Payments
# ===========================================================================


def _po_supplier_summary(purchase_order):
    """Return (payments_qs, total_paid, balance_due) for a PO."""
    payments = purchase_order.supplier_payments.select_related("created_by").order_by(
        "-paid_at", "-id"
    )
    total_paid = payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    subtotal = purchase_order.subtotal or Decimal("0.00")
    balance_due = max(subtotal - total_paid, Decimal("0.00"))
    return payments, total_paid, balance_due


@login_required
@role_required("ADMIN", "DIRECTOR", "FINANCE", "PROCUREMENT")
def record_supplier_payment(request, po_pk):
    purchase_order = get_object_or_404(
        PurchaseOrder.objects.select_related("transaction"), pk=po_pk
    )
    if purchase_order.transaction.is_closed:
        messages.error(
            request,
            "This trade is closed; supplier payments cannot be recorded.",
        )
        return redirect("purchase_order_detail", pk=purchase_order.pk)

    if request.method == "POST":
        form = SupplierPaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.purchase_order = purchase_order
            if not payment.supplier_name:
                payment.supplier_name = purchase_order.supplier_name
            payment.created_by = request.user
            payment.save()
            log_audit(
                "supplier_payment",
                "create",
                payment.id,
                f"{purchase_order.po_number} {payment.amount} {payment.currency}",
                request.user,
            )
            _notify_roles(
                title="Supplier payment recorded",
                message=(
                    f"{payment.amount} {payment.currency} paid to "
                    f"{payment.supplier_name or purchase_order.supplier_name} "
                    f"against {purchase_order.po_number}."
                ),
                link=f"/purchase-orders/{purchase_order.pk}/",
                category="trading",
                roles=["ADMIN", "DIRECTOR", "FINANCE", "PROCUREMENT"],
            )
            messages.success(request, "Supplier payment recorded.")
            return redirect("purchase_order_detail", pk=purchase_order.pk)
    else:
        form = SupplierPaymentForm(
            initial={
                "supplier_name": purchase_order.supplier_name,
                "currency": "USD",
                "paid_at": timezone.now(),
            }
        )

    payments, total_paid, balance_due = _po_supplier_summary(purchase_order)
    return render(
        request,
        "logistics/invoicing/supplier_payment_form.html",
        {
            "form": form,
            "purchase_order": purchase_order,
            "payments": payments,
            "total_paid": total_paid,
            "balance_due": balance_due,
        },
    )


@login_required
@role_required("ADMIN", "DIRECTOR", "FINANCE", "PROCUREMENT")
def supplier_payment_list(request):
    qs = SupplierPayment.objects.select_related(
        "purchase_order__transaction__customer", "created_by"
    ).order_by("-paid_at", "-id")
    search = (request.GET.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(purchase_order__po_number__icontains=search)
            | Q(supplier_name__icontains=search)
            | Q(reference__icontains=search)
            | Q(purchase_order__transaction__transaction_id__icontains=search)
        )
    page_obj, query_string, page_range = paginate_queryset(request, qs)
    totals = qs.aggregate(total=Sum("amount"))
    return render(
        request,
        "logistics/invoicing/supplier_payment_list.html",
        {
            "payments": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "page_range": page_range,
            "search": search,
            "grand_total": totals["total"] or Decimal("0.00"),
        },
    )


@login_required
@role_required("ADMIN", "DIRECTOR")
def supplier_payment_delete(request, pk):
    payment = get_object_or_404(
        SupplierPayment.objects.select_related("purchase_order"), pk=pk
    )
    po_pk = payment.purchase_order_id
    if request.method == "POST":
        log_audit(
            "supplier_payment",
            "delete",
            payment.id,
            f"{payment.purchase_order.po_number} {payment.amount}",
            request.user,
        )
        payment.delete()
        messages.success(request, "Supplier payment removed.")
        return redirect("purchase_order_detail", pk=po_pk)
    return render(
        request,
        "logistics/invoicing/supplier_payment_confirm_delete.html",
        {"payment": payment},
    )
