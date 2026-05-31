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
    GeneralInvoice,
    GeneralPayment,
    GeneralQuotation,
    GeneralReceipt,
    InventoryItem,
    Loading,
    Payment,
    PaymentTransaction,
    ProformaInvoice,
    ProofOfDelivery,
    Receipt,
    DocumentSignature,
    SignatureProfile,
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
    BillingCharge,
    BillingInvoiceLine,
    DocumentArchive,
    DomainEvent,
    InventoryMovement,
    InventoryPosition,
    Notification,
    NoticeboardTask,
    PurchaseOrder,
    WorkflowTransitionLog,
)
from .services import (
    WorkflowTransitionError,
    transition_cargo_item,
    transition_shipment,
)

admin.site.site_header = "GMI Terralink Administration"
admin.site.site_title = "GMI Terralink Admin"
admin.site.index_title = "Operations Control Center"


def _admin_dashboard_has_permission(request):
    user = request.user
    return bool(
        user.is_active
        and user.is_staff
        and (user.is_superuser or getattr(user, "role", "") == "ADMIN")
    )


admin.site.has_permission = _admin_dashboard_has_permission


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Custom user admin"""

    protected_admin_fields = (
        "is_staff",
        "is_superuser",
        "role",
        "groups",
        "user_permissions",
    )

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
                "fields": (
                    "username",
                    "email",
                    "first_name",
                    "last_name",
                    "phone",
                    "password1",
                    "password2",
                    "role",
                ),
            },
        ),
    )
    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff")
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("username", "first_name", "last_name", "email")

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj and (obj.is_superuser or obj.role == "ADMIN"):
            readonly_fields.extend(
                field
                for field in self.protected_admin_fields
                if field not in readonly_fields
            )
        return readonly_fields

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        role_field = form.base_fields.get("role")
        if role_field:
            role_field.choices = [
                (value, label)
                for value, label in role_field.choices
                if value != "ADMIN"
            ]
        return form

    def save_model(self, request, obj, form, change):
        original = CustomUser.objects.filter(pk=obj.pk).first() if obj.pk else None
        if original and (original.is_superuser or original.role == "ADMIN"):
            obj.is_staff = original.is_staff
            obj.is_superuser = original.is_superuser
            obj.role = original.role
        elif obj.role == "ADMIN" or obj.is_superuser:
            messages.error(request, "Accounts cannot be promoted to System Admin here.")
            obj.is_superuser = False
            obj.is_staff = False
            obj.role = original.role if original else "OFFICE_ADMIN"
        super().save_model(request, obj, form, change)


@admin.register(SignatureProfile)
class SignatureProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "title", "is_active", "updated_at")
    list_filter = ("is_active", "updated_at")
    search_fields = ("user__username", "user__first_name", "user__last_name", "title")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("user",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "recipient", "category", "is_read", "created_at")
    list_filter = ("category", "is_read", "created_at")
    search_fields = ("title", "message", "recipient__username", "recipient__email")
    raw_id_fields = ("recipient",)
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    list_select_related = ("recipient",)


@admin.register(NoticeboardTask)
class NoticeboardTaskAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "assigned_to",
        "assigned_role",
        "is_done",
        "created_by",
        "created_at",
    )
    list_filter = ("is_done", "assigned_role", "created_at", "completed_at")
    search_fields = (
        "title",
        "description",
        "assigned_to__username",
        "assigned_to__email",
        "created_by__username",
    )
    raw_id_fields = ("assigned_to", "created_by", "completed_by")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    list_select_related = ("assigned_to", "created_by", "completed_by")


@admin.register(DocumentSignature)
class DocumentSignatureAdmin(admin.ModelAdmin):
    list_display = (
        "content_object",
        "signer_name",
        "signer_role",
        "signed_by",
        "signed_at",
    )
    list_filter = ("signer_role", "signed_at")
    search_fields = (
        "signer_name",
        "signer_role",
        "signed_by__username",
        "signed_by__first_name",
        "signed_by__last_name",
    )
    readonly_fields = (
        "content_type",
        "object_id",
        "signed_by",
        "signature_profile",
        "signer_name",
        "signer_title",
        "signer_role",
        "note",
        "signed_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "receipt_number",
        "payment",
        "amount",
        "payment_method",
        "verification_status",
        "payment_date",
        "created_by",
    )
    list_filter = ("verification_status", "payment_method", "payment_date")
    search_fields = (
        "reference",
        "payment__loading__loading_id",
        "payment__loading__client__name",
        "created_by__username",
    )
    raw_id_fields = ("payment", "created_by", "verified_by")
    readonly_fields = ("receipt_number", "created_at", "updated_at")
    date_hierarchy = "payment_date"
    list_select_related = ("payment", "created_by", "verified_by")


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


@admin.register(DocumentArchive)
class DocumentArchiveAdmin(admin.ModelAdmin):
    list_display = (
        "original_filename",
        "document_type",
        "transaction",
        "source_label",
        "archived_by",
        "created_at",
    )
    list_filter = ("document_type", "source_model", "created_at")
    search_fields = (
        "original_filename",
        "source_label",
        "source_model",
        "source_object_id",
        "transaction__transaction_id",
        "archived_by__username",
    )
    raw_id_fields = ("document", "transaction", "archived_by")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    list_select_related = ("document", "transaction", "archived_by")


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


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        "po_number",
        "transaction",
        "supplier_name",
        "status",
        "subtotal",
        "created_at",
    )
    list_filter = ("status", "split_mode", "created_at")
    search_fields = (
        "po_number",
        "supplier_name",
        "transaction__transaction_id",
        "transaction__customer__name",
    )
    raw_id_fields = (
        "transaction",
        "proforma",
        "final_invoice",
        "parent_po",
        "created_by",
    )
    readonly_fields = ("po_number", "created_at", "updated_at")
    date_hierarchy = "created_at"
    list_select_related = ("transaction", "created_by", "parent_po")


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


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ("client", "amount", "currency", "date", "created_by", "created_at")
    list_filter = ("currency", "date", "created_at")
    search_fields = (
        "client__name",
        "client__client_id",
        "notes",
        "created_by__username",
    )
    raw_id_fields = ("client", "created_by")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "date"
    list_select_related = ("client", "created_by")


@admin.register(ProofOfDelivery)
class ProofOfDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "pod_number",
        "target_reference",
        "business_side",
        "received_by_name",
        "delivered_at",
        "created_by",
    )
    list_filter = ("delivered_at", "created_at")
    search_fields = (
        "pod_number",
        "received_by_name",
        "received_by_phone",
        "loading__loading_id",
        "fulfillment_order__transaction__transaction_id",
    )
    raw_id_fields = ("loading", "fulfillment_order", "created_by")
    readonly_fields = ("pod_number", "created_at", "updated_at")
    date_hierarchy = "delivered_at"
    list_select_related = ("loading", "fulfillment_order", "created_by")


@admin.register(GeneralQuotation)
class GeneralQuotationAdmin(admin.ModelAdmin):
    list_display = ("quotation_number", "client", "purpose", "status", "total_amount", "currency", "created_at")
    list_filter = ("status", "purpose", "currency", "created_at")
    search_fields = ("quotation_number", "client__name", "custom_purpose")
    readonly_fields = ("quotation_number", "created_at", "updated_at")
    raw_id_fields = ("client", "transaction", "created_by")


@admin.register(GeneralInvoice)
class GeneralInvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "client", "purpose", "status", "total_amount", "amount_paid", "balance", "created_at")
    list_filter = ("status", "purpose", "currency", "created_at")
    search_fields = ("invoice_number", "client__name", "custom_purpose")
    readonly_fields = ("invoice_number", "amount_paid", "balance", "created_at", "updated_at")
    raw_id_fields = ("client", "transaction", "quotation", "created_by")


@admin.register(GeneralPayment)
class GeneralPaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "amount", "currency", "method", "reference", "paid_at", "created_by")
    list_filter = ("method", "currency", "paid_at")
    search_fields = ("invoice__invoice_number", "reference", "invoice__client__name")
    raw_id_fields = ("invoice", "created_by")


@admin.register(GeneralReceipt)
class GeneralReceiptAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "issued_to", "amount", "currency", "purpose", "issued_at")
    list_filter = ("currency", "issued_at")
    search_fields = ("receipt_number", "issued_to", "payment__invoice__invoice_number")
    readonly_fields = ("receipt_number", "payment", "amount", "currency", "issued_to", "purpose", "issued_at")
    raw_id_fields = ("payment",)


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


@admin.register(InventoryPosition)
class InventoryPositionAdmin(admin.ModelAdmin):
    list_display = (
        "cargo_item",
        "qty_warehouse",
        "qty_reserved",
        "qty_in_transit",
        "qty_delivered",
        "version",
        "updated_at",
    )
    list_filter = ("updated_at",)
    search_fields = ("cargo_item__cargo_number", "cargo_item__description")
    raw_id_fields = ("cargo_item",)
    readonly_fields = ("updated_at",)
    list_select_related = ("cargo_item",)


@admin.register(DomainEvent)
class DomainEventAdmin(admin.ModelAdmin):
    list_display = (
        "event_type",
        "aggregate_type",
        "aggregate_id",
        "created_by",
        "processed_at",
        "created_at",
    )
    list_filter = ("aggregate_type", "event_type", "processed_at", "created_at")
    search_fields = ("event_type", "aggregate_type", "aggregate_id", "idempotency_key")
    raw_id_fields = ("created_by",)
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    list_select_related = ("created_by",)


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = (
        "cargo_item",
        "shipment",
        "movement_type",
        "quantity",
        "from_state",
        "to_state",
        "created_at",
    )
    list_filter = ("movement_type", "from_state", "to_state", "created_at")
    search_fields = (
        "cargo_item__cargo_number",
        "shipment__shipment_number",
        "idempotency_key",
    )
    raw_id_fields = ("position", "cargo_item", "shipment", "event", "created_by")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    list_select_related = ("position", "cargo_item", "shipment", "event", "created_by")


@admin.register(WorkflowTransitionLog)
class WorkflowTransitionLogAdmin(admin.ModelAdmin):
    list_display = (
        "entity_type",
        "entity_id",
        "from_status",
        "to_status",
        "created_by",
        "created_at",
    )
    list_filter = ("entity_type", "from_status", "to_status", "created_at")
    search_fields = ("entity_id", "notes", "created_by__username")
    raw_id_fields = ("event", "created_by")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    list_select_related = ("event", "created_by")


@admin.register(BillingCharge)
class BillingChargeAdmin(admin.ModelAdmin):
    list_display = (
        "shipment",
        "cargo_item",
        "charge_type",
        "status",
        "quantity",
        "unit_price",
        "amount",
        "currency",
        "created_at",
    )
    list_filter = ("charge_type", "status", "currency", "created_at")
    search_fields = (
        "shipment__shipment_number",
        "cargo_item__cargo_number",
        "trigger_event",
        "idempotency_key",
    )
    raw_id_fields = ("shipment", "cargo_item", "event")
    readonly_fields = ("amount", "created_at")
    date_hierarchy = "created_at"
    list_select_related = ("shipment", "cargo_item", "event")


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


@admin.register(BillingInvoiceLine)
class BillingInvoiceLineAdmin(admin.ModelAdmin):
    list_display = ("invoice", "description", "quantity", "unit_price", "amount")
    search_fields = (
        "invoice__invoice_number",
        "description",
        "charge__idempotency_key",
    )
    raw_id_fields = ("invoice", "charge")
    list_select_related = ("invoice", "charge")


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
    list_display = (
        "purchase_order",
        "supplier_name",
        "amount",
        "currency",
        "method",
        "paid_at",
        "created_by",
    )
    list_filter = ("currency", "method", "paid_at")
    search_fields = ("purchase_order__po_number", "supplier_name", "reference")
    raw_id_fields = ("purchase_order",)
    readonly_fields = ("created_at", "updated_at")
