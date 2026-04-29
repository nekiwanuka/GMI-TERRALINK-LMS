"""
Django admin configuration for the logistics app
"""

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from .models import (
    AuditLog,
    Client,
    Commission,
    ContainerReturn,
    CustomUser,
    Document,
    FinalInvoice,
    FulfillmentLine,
    FulfillmentOrder,
    InventoryItem,
    Loading,
    Payment,
    PaymentTransaction,
    ProformaInvoice,
    ProofOfDelivery,
    Receipt,
    Sourcing,
    Supplier,
    SupplierPayment,
    SupplierProduct,
    BillingInvoice,
    BillingPayment,
    CargoItemWorkflow,
    ShipmentWorkflow,
    Transaction,
    TransactionPaymentRecord,
    Transit,
    ShipmentLeg,
)
from .services import (
    WorkflowTransitionError,
    transition_cargo_item,
    transition_shipment,
)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Custom user admin"""

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email", "phone")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "role",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2", "role"),
            },
        ),
    )
    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff")
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("username", "first_name", "last_name", "email")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """Client admin"""

    list_display = ("client_id", "name", "contact_person", "phone", "date_registered")
    search_fields = ("client_id", "name", "contact_person")
    list_filter = ("date_registered",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Loading)
class LoadingAdmin(admin.ModelAdmin):
    """Loading admin"""

    list_display = ("loading_id", "client", "loading_date", "origin", "destination")
    search_fields = ("loading_id", "client__name")
    list_filter = ("loading_date", "origin", "destination")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Transit)
class TransitAdmin(admin.ModelAdmin):
    """Transit admin"""

    list_display = ("vessel_name", "loading", "boarding_date", "eta_kampala", "status")
    search_fields = ("vessel_name", "loading__loading_id")
    list_filter = ("status", "boarding_date")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Payment admin"""

    list_display = (
        "loading",
        "amount_charged",
        "amount_paid",
        "balance",
        "payment_date",
    )
    search_fields = ("loading__loading_id", "receipt_number")
    list_filter = ("payment_date", "payment_method")
    readonly_fields = ("balance", "created_at", "updated_at")


@admin.register(ContainerReturn)
class ContainerReturnAdmin(admin.ModelAdmin):
    """Container return admin"""

    list_display = ("container_number", "loading", "return_date", "condition", "status")
    search_fields = ("container_number", "loading__loading_id")
    list_filter = ("status", "condition", "return_date")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Audit log admin - Read only"""

    list_display = ("timestamp", "user", "action", "model_type", "object_str")
    search_fields = ("user__username", "object_str")
    list_filter = ("action", "model_type", "timestamp")
    readonly_fields = (
        "user",
        "model_type",
        "action",
        "object_id",
        "object_str",
        "changes",
        "timestamp",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_person", "phone", "email")
    search_fields = ("name", "contact_person", "phone", "email")


@admin.register(SupplierProduct)
class SupplierProductAdmin(admin.ModelAdmin):
    list_display = (
        "supplier",
        "product_name",
        "min_order_quantity",
        "unit_price",
        "resale_price",
    )
    search_fields = ("supplier__name", "product_name")


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        "item_code",
        "item_name",
        "transaction",
        "quantity_in_warehouse",
        "stock_status",
        "supplier",
    )
    list_filter = ("stock_status",)
    search_fields = (
        "item_code",
        "item_name",
        "transaction__transaction_id",
        "transaction__customer__name",
    )


@admin.register(FulfillmentOrder)
class FulfillmentOrderAdmin(admin.ModelAdmin):
    list_display = (
        "transaction",
        "status",
        "port_of_loading",
        "destination_port",
        "planned_delivery_date",
    )
    list_filter = ("status",)
    search_fields = ("transaction__transaction_id", "transaction__customer__name")


@admin.register(FulfillmentLine)
class FulfillmentLineAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "inventory_item",
        "quantity_allocated",
        "quantity_dispatched",
        "quantity_delivered",
    )
    search_fields = (
        "order__transaction__transaction_id",
        "inventory_item__item_code",
        "inventory_item__item_name",
    )


@admin.register(ShipmentLeg)
class ShipmentLegAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "sequence",
        "leg_type",
        "origin",
        "destination",
        "status",
    )
    list_filter = ("leg_type", "status")
    search_fields = ("order__transaction__transaction_id", "origin", "destination")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_id",
        "customer",
        "status",
        "estimated_delivery",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("transaction_id", "customer__name", "customer__client_id")
    readonly_fields = ("transaction_id", "created_at", "updated_at")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("transaction", "document_type", "uploaded_by", "timestamp")
    list_filter = ("document_type", "timestamp")
    search_fields = ("transaction__transaction_id",)
    readonly_fields = ("timestamp",)


@admin.register(Sourcing)
class SourcingAdmin(admin.ModelAdmin):
    list_display = ("transaction", "supplier_name", "created_by", "created_at")
    search_fields = ("transaction__transaction_id", "supplier_name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProformaInvoice)
class ProformaInvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "transaction", "subtotal", "validity_date", "status")
    list_filter = ("status", "validity_date")
    readonly_fields = ("created_at", "updated_at")


@admin.register(FinalInvoice)
class FinalInvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "transaction", "total_amount", "currency", "is_confirmed")
    list_filter = ("currency", "shipping_mode", "is_confirmed")
    readonly_fields = ("total_amount", "confirmed_at", "created_at", "updated_at")


@admin.register(TransactionPaymentRecord)
class TransactionPaymentRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "transaction",
        "is_full_payment",
        "amount_due_snapshot",
        "amount",
        "cash_received",
        "change_given",
        "balance_after",
        "currency",
        "payment_date",
        "payment_method",
        "created_by",
    )
    list_filter = ("currency", "payment_method", "payment_date")
    search_fields = ("transaction__transaction_id", "reference")
    readonly_fields = ("created_at",)


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "receipt_number",
        "issued_to",
        "amount",
        "currency",
        "issued_at",
        "is_reversed",
    )
    list_filter = ("currency", "is_reversed", "issued_at")
    search_fields = ("receipt_number", "issued_to")
    readonly_fields = (
        "receipt_number",
        "amount",
        "currency",
        "issued_to",
        "issued_at",
        "logistics_payment",
        "sourcing_payment",
        "reversed_at",
        "reversed_by",
    )


@admin.register(ShipmentWorkflow)
class ShipmentWorkflowAdmin(admin.ModelAdmin):
    list_display = (
        "shipment_number",
        "mode",
        "client",
        "status",
        "origin",
        "destination",
        "created_at",
    )
    list_filter = ("mode", "status", "created_at")
    search_fields = ("shipment_number", "client__name", "origin", "destination")
    readonly_fields = ("shipment_number", "status", "created_at", "updated_at")
    actions = [
        "mark_verified",
        "mark_allocated",
        "mark_loaded",
        "mark_in_transit",
        "mark_arrived",
        "mark_delivered",
    ]

    def _transition_queryset(self, request, queryset, to_status):
        succeeded = 0
        for shipment in queryset:
            try:
                transition_shipment(
                    shipment=shipment,
                    to_status=to_status,
                    actor=request.user,
                    notes=f"Admin action transition to {to_status}",
                )
                succeeded += 1
            except WorkflowTransitionError as exc:
                self.message_user(
                    request,
                    f"{shipment.shipment_number}: {exc}",
                    level=messages.ERROR,
                )
        if succeeded:
            self.message_user(
                request,
                f"Transitioned {succeeded} shipment(s) to {to_status}.",
            )

    def mark_verified(self, request, queryset):
        self._transition_queryset(request, queryset, "VERIFIED")

    def mark_allocated(self, request, queryset):
        self._transition_queryset(request, queryset, "ALLOCATED")

    def mark_loaded(self, request, queryset):
        self._transition_queryset(request, queryset, "LOADED")

    def mark_in_transit(self, request, queryset):
        self._transition_queryset(request, queryset, "IN_TRANSIT")

    def mark_arrived(self, request, queryset):
        self._transition_queryset(request, queryset, "ARRIVED")

    def mark_delivered(self, request, queryset):
        self._transition_queryset(request, queryset, "DELIVERED")


@admin.register(CargoItemWorkflow)
class CargoItemWorkflowAdmin(admin.ModelAdmin):
    list_display = (
        "cargo_number",
        "shipment",
        "status",
        "inventory_state",
        "quantity_total",
        "quantity_delivered",
    )
    list_filter = ("status", "inventory_state", "created_at")
    search_fields = ("cargo_number", "shipment__shipment_number", "description")
    readonly_fields = (
        "cargo_number",
        "status",
        "inventory_state",
        "created_at",
        "updated_at",
    )
    actions = [
        "mark_verified",
        "mark_allocated",
        "mark_loaded",
        "mark_in_transit",
        "mark_arrived",
        "mark_delivered",
    ]

    def _transition_queryset(self, request, queryset, to_status):
        succeeded = 0
        for cargo_item in queryset:
            try:
                transition_cargo_item(
                    cargo_item=cargo_item,
                    to_status=to_status,
                    actor=request.user,
                    notes=f"Admin action transition to {to_status}",
                )
                succeeded += 1
            except WorkflowTransitionError as exc:
                self.message_user(
                    request,
                    f"{cargo_item.cargo_number}: {exc}",
                    level=messages.ERROR,
                )
        if succeeded:
            self.message_user(
                request,
                f"Transitioned {succeeded} cargo item(s) to {to_status}.",
            )

    def mark_verified(self, request, queryset):
        self._transition_queryset(request, queryset, "VERIFIED")

    def mark_allocated(self, request, queryset):
        self._transition_queryset(request, queryset, "ALLOCATED")

    def mark_loaded(self, request, queryset):
        self._transition_queryset(request, queryset, "LOADED")

    def mark_in_transit(self, request, queryset):
        self._transition_queryset(request, queryset, "IN_TRANSIT")

    def mark_arrived(self, request, queryset):
        self._transition_queryset(request, queryset, "ARRIVED")

    def mark_delivered(self, request, queryset):
        self._transition_queryset(request, queryset, "DELIVERED")


@admin.register(BillingInvoice)
class BillingInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "shipment",
        "client",
        "status",
        "total_amount",
        "amount_paid",
        "balance",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("invoice_number", "shipment__shipment_number", "client__name")
    readonly_fields = (
        "invoice_number",
        "subtotal",
        "tax_amount",
        "total_amount",
        "amount_paid",
        "balance",
        "created_at",
        "updated_at",
    )


@admin.register(BillingPayment)
class BillingPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "invoice",
        "amount",
        "method",
        "reference",
        "paid_at",
        "created_by",
    )
    list_filter = ("method", "paid_at")
    search_fields = ("invoice__invoice_number", "reference")
    readonly_fields = ("idempotency_key", "paid_at")

@admin.register(SupplierPayment)
class SupplierPaymentAdmin(admin.ModelAdmin):
    list_display = ("purchase_order", "supplier_name", "amount", "currency", "method", "paid_at", "created_by")
    list_filter = ("currency", "method", "paid_at")
    search_fields = ("purchase_order__po_number", "supplier_name", "reference")
    raw_id_fields = ("purchase_order",)
    readonly_fields = ("created_at", "updated_at")
