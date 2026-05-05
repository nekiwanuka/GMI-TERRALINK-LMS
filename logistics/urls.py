"""
URL configuration for the logistics app
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from .viewsets import (
    BillingInvoiceViewSet,
    CargoItemWorkflowViewSet,
    ShipmentWorkflowViewSet,
)

router = DefaultRouter()
router.register(
    "workflow/shipments", ShipmentWorkflowViewSet, basename="workflow-shipment"
)
router.register(
    "workflow/cargo-items", CargoItemWorkflowViewSet, basename="workflow-cargo"
)
router.register("workflow/invoices", BillingInvoiceViewSet, basename="workflow-invoice")

urlpatterns = [
    path("api/", include(router.urls)),
    # Authentication
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("set-lane/", views.set_lane, name="set_lane"),
    path(
        "notifications/read-all/",
        views.notifications_mark_all_read,
        name="notifications_mark_all_read",
    ),
    path("register/", views.register_view, name="register"),
    path("signatures/profile/", views.signature_profile, name="signature_profile"),
    path("protected-media/<path:path>", views.protected_media, name="protected_media"),
    # Dashboard
    path("", views.dashboard, name="dashboard"),
    # Users
    path("users/", views.user_list, name="user_list"),
    # Clients
    path("clients/", views.client_list, name="client_list"),
    path("clients/create/", views.client_create, name="client_create"),
    path("clients/<int:pk>/", views.client_detail, name="client_detail"),
    path("clients/<int:pk>/update/", views.client_update, name="client_update"),
    path("clients/<int:pk>/delete/", views.client_delete, name="client_delete"),
    # Commissions (Director / System Admin only)
    path("commissions/", views.commission_list, name="commission_list"),
    path("commissions/create/", views.commission_create, name="commission_create"),
    path(
        "commissions/<int:pk>/update/",
        views.commission_update,
        name="commission_update",
    ),
    path(
        "commissions/<int:pk>/delete/",
        views.commission_delete,
        name="commission_delete",
    ),
    # Proof of Delivery (shared between logistics and trading lanes)
    path(
        "loadings/<int:loading_pk>/pod/record/",
        views.record_logistics_pod,
        name="record_logistics_pod",
    ),
    path(
        "fulfillment/<int:fulfillment_pk>/pod/record/",
        views.record_trading_pod,
        name="record_trading_pod",
    ),
    path("pod/", views.pod_list, name="pod_list"),
    path("pod/<int:pk>/", views.pod_detail, name="pod_detail"),
    path("track/<str:token>/", views.public_track, name="public_track"),
    path(
        "pod/<int:pk>/delivery-note/",
        views.pod_delivery_note_pdf,
        name="pod_delivery_note_pdf",
    ),
    # Loadings
    path("loadings/", views.loading_list, name="loading_list"),
    path("loadings/create/", views.loading_create, name="loading_create"),
    path("loadings/<int:pk>/", views.loading_detail, name="loading_detail"),
    path(
        "loadings/<int:pk>/start-flow/",
        views.loading_start_flow,
        name="loading_start_flow",
    ),
    path(
        "loadings/<int:pk>/document/",
        views.loading_document,
        name="loading_document",
    ),
    path(
        "loadings/<int:pk>/packing-list/",
        views.loading_packing_list_document,
        name="loading_packing_list_document",
    ),
    path("loadings/<int:pk>/update/", views.loading_update, name="loading_update"),
    path("loadings/<int:pk>/delete/", views.loading_delete, name="loading_delete"),
    # Transits
    path("transits/", views.transit_list, name="transit_list"),
    path("transits/create/", views.transit_create, name="transit_create"),
    path(
        "transits/create/<int:loading_id>/",
        views.transit_create,
        name="transit_create_with_loading",
    ),
    path("transits/<int:pk>/update/", views.transit_update, name="transit_update"),
    path("transits/<int:pk>/", views.transit_detail, name="transit_detail"),
    # Payments
    path("payments/", views.payment_list, name="payment_list"),
    path("payments/create/", views.payment_create, name="payment_create"),
    path(
        "payments/create/<int:loading_id>/",
        views.payment_create,
        name="payment_create_with_loading",
    ),
    path("payments/<int:pk>/", views.payment_detail, name="payment_detail"),
    path("payments/<int:pk>/update/", views.payment_update, name="payment_update"),
    path("payments/<int:pk>/invoice/", views.payment_invoice, name="payment_invoice"),
    path(
        "payments/transactions/<int:transaction_id>/receipt/",
        views.payment_receipt,
        name="payment_receipt",
    ),
    # Transactions
    path("transactions/", views.transaction_list, name="transaction_list"),
    path("transactions/create/", views.transaction_create, name="transaction_create"),
    path("transactions/<int:pk>/", views.transaction_detail, name="transaction_detail"),
    path("fulfillment/", views.fulfillment_list, name="fulfillment_list"),
    path(
        "fulfillment/<int:pk>/timeline/",
        views.fulfillment_timeline,
        name="fulfillment_timeline",
    ),
    path(
        "transactions/<int:transaction_pk>/fulfillment/create/",
        views.fulfillment_order_create,
        name="fulfillment_order_create",
    ),
    path(
        "transactions/<int:pk>/update/",
        views.transaction_update,
        name="transaction_update",
    ),
    path(
        "transactions/<int:pk>/close/",
        views.close_transaction,
        name="close_transaction",
    ),
    path(
        "transactions/<int:pk>/reopen/",
        views.reopen_transaction,
        name="reopen_transaction",
    ),
    path("loadings/<int:pk>/close/", views.close_loading, name="close_loading"),
    path("loadings/<int:pk>/reopen/", views.reopen_loading, name="reopen_loading"),
    path(
        "fulfillment/<int:pk>/update/",
        views.fulfillment_order_update,
        name="fulfillment_order_update",
    ),
    path(
        "fulfillment/<int:order_pk>/lines/create/",
        views.fulfillment_line_create,
        name="fulfillment_line_create",
    ),
    path(
        "fulfillment/lines/<int:pk>/update/",
        views.fulfillment_line_update,
        name="fulfillment_line_update",
    ),
    path(
        "fulfillment/<int:order_pk>/legs/create/",
        views.shipment_leg_create,
        name="shipment_leg_create",
    ),
    path(
        "fulfillment/legs/<int:pk>/update/",
        views.shipment_leg_update,
        name="shipment_leg_update",
    ),
    path(
        "transactions/<int:pk>/documents/upload/",
        views.transaction_document_upload,
        name="transaction_document_upload",
    ),
    path(
        "documents/<int:pk>/edit-pi/",
        views.document_edit_pi,
        name="document_edit_pi",
    ),
    path(
        "documents/archive/", views.document_archive_list, name="document_archive_list"
    ),
    # Sourcing Module
    path("sourcing/", views.sourcing_list, name="sourcing_list"),
    path("sourcing/create/", views.sourcing_create, name="sourcing_create"),
    path("sourcing/<int:pk>/update/", views.sourcing_update, name="sourcing_update"),
    path("sourcing/<int:pk>/pdf/", views.sourcing_pdf, name="sourcing_pdf"),
    # Warehouse Module (storage tracking for purchased items)
    path("inventory/", views.inventory_list, name="inventory_list"),
    path("inventory/create/", views.inventory_create, name="inventory_create"),
    path("inventory/<int:pk>/update/", views.inventory_update, name="inventory_update"),
    path("warehouse/", views.inventory_list, name="warehouse_list"),
    path("warehouse/create/", views.inventory_create, name="warehouse_create"),
    path("warehouse/<int:pk>/update/", views.inventory_update, name="warehouse_update"),
    path("suppliers/", views.supplier_list, name="supplier_list"),
    path("suppliers/<int:pk>/update/", views.supplier_update, name="supplier_update"),
    path(
        "suppliers/<int:supplier_pk>/products/create/",
        views.supplier_product_create,
        name="supplier_product_create",
    ),
    path(
        "suppliers/<int:supplier_pk>/products/<int:product_pk>/delete/",
        views.supplier_product_delete,
        name="supplier_product_delete",
    ),
    path("inventory/suppliers/create/", views.supplier_create, name="supplier_create"),
    path(
        "warehouse/suppliers/create/",
        views.supplier_create,
        name="warehouse_supplier_create",
    ),
    # Invoicing Module
    path(
        "logistics/invoicing/proformas/",
        views.proforma_list,
        name="logistics_proforma_list",
    ),
    path(
        "logistics/invoicing/proformas/create/",
        views.proforma_create,
        name="logistics_proforma_create",
    ),
    path(
        "logistics/invoicing/proformas/<int:pk>/",
        views.proforma_detail,
        name="logistics_proforma_detail",
    ),
    path(
        "logistics/invoicing/proformas/<int:pk>/update/",
        views.proforma_update,
        name="logistics_proforma_update",
    ),
    path(
        "logistics/invoicing/proformas/<int:pk>/confirm/",
        views.proforma_confirm,
        name="logistics_proforma_confirm",
    ),
    path(
        "logistics/invoicing/proformas/<int:pk>/pdf/",
        views.proforma_pdf,
        name="logistics_proforma_pdf",
    ),
    path(
        "logistics/invoicing/proformas/<int:pk>/html-preview/",
        views.proforma_html_preview,
        name="logistics_proforma_html_preview",
    ),
    path(
        "logistics/invoicing/final/",
        views.final_invoice_list,
        name="logistics_final_invoice_list",
    ),
    path(
        "logistics/invoicing/final/create/",
        views.final_invoice_create,
        name="logistics_final_invoice_create",
    ),
    path(
        "logistics/invoicing/final/<int:pk>/",
        views.final_invoice_detail,
        name="logistics_final_invoice_detail",
    ),
    path(
        "logistics/invoicing/final/<int:pk>/update/",
        views.final_invoice_update,
        name="logistics_final_invoice_update",
    ),
    path(
        "logistics/invoicing/final/<int:pk>/pdf/",
        views.final_invoice_pdf,
        name="logistics_final_invoice_pdf",
    ),
    path(
        "logistics/invoicing/final/<int:pk>/html-preview/",
        views.final_invoice_html_preview,
        name="logistics_final_invoice_html_preview",
    ),
    path(
        "logistics/invoicing/final/<int:pk>/generate-po/",
        views.final_invoice_generate_purchase_order,
        name="logistics_final_invoice_generate_po",
    ),
    path(
        "sourcing/invoicing/proformas/",
        views.proforma_list,
        name="sourcing_proforma_list",
    ),
    path(
        "sourcing/invoicing/proformas/create/",
        views.proforma_create,
        name="sourcing_proforma_create",
    ),
    path(
        "sourcing/invoicing/proformas/<int:pk>/",
        views.proforma_detail,
        name="sourcing_proforma_detail",
    ),
    path(
        "sourcing/invoicing/proformas/<int:pk>/update/",
        views.proforma_update,
        name="sourcing_proforma_update",
    ),
    path(
        "sourcing/invoicing/proformas/<int:pk>/confirm/",
        views.proforma_confirm,
        name="sourcing_proforma_confirm",
    ),
    path(
        "sourcing/invoicing/proformas/<int:pk>/pdf/",
        views.proforma_pdf,
        name="sourcing_proforma_pdf",
    ),
    path(
        "sourcing/invoicing/proformas/<int:pk>/html-preview/",
        views.proforma_html_preview,
        name="sourcing_proforma_html_preview",
    ),
    path(
        "sourcing/invoicing/final/",
        views.final_invoice_list,
        name="sourcing_final_invoice_list",
    ),
    path(
        "sourcing/invoicing/final/create/",
        views.final_invoice_create,
        name="sourcing_final_invoice_create",
    ),
    path(
        "sourcing/invoicing/final/<int:pk>/",
        views.final_invoice_detail,
        name="sourcing_final_invoice_detail",
    ),
    path(
        "sourcing/invoicing/final/<int:pk>/update/",
        views.final_invoice_update,
        name="sourcing_final_invoice_update",
    ),
    path(
        "sourcing/invoicing/final/<int:pk>/pdf/",
        views.final_invoice_pdf,
        name="sourcing_final_invoice_pdf",
    ),
    path(
        "sourcing/invoicing/final/<int:pk>/html-preview/",
        views.final_invoice_html_preview,
        name="sourcing_final_invoice_html_preview",
    ),
    path(
        "sourcing/invoicing/final/<int:pk>/generate-po/",
        views.final_invoice_generate_purchase_order,
        name="sourcing_final_invoice_generate_po",
    ),
    path("invoicing/proformas/", views.proforma_list, name="proforma_list"),
    path("invoicing/proformas/create/", views.proforma_create, name="proforma_create"),
    path(
        "invoicing/proformas/<int:pk>/", views.proforma_detail, name="proforma_detail"
    ),
    path(
        "invoicing/proformas/<int:pk>/sign/", views.proforma_sign, name="proforma_sign"
    ),
    path(
        "invoicing/proformas/<int:pk>/update/",
        views.proforma_update,
        name="proforma_update",
    ),
    path(
        "invoicing/proformas/<int:pk>/confirm/",
        views.proforma_confirm,
        name="proforma_confirm",
    ),
    path("invoicing/proformas/<int:pk>/pdf/", views.proforma_pdf, name="proforma_pdf"),
    path(
        "invoicing/proformas/<int:pk>/html-preview/",
        views.proforma_html_preview,
        name="proforma_html_preview",
    ),
    path("invoicing/final/", views.final_invoice_list, name="final_invoice_list"),
    path(
        "invoicing/final/create/",
        views.final_invoice_create,
        name="final_invoice_create",
    ),
    path(
        "invoicing/final/<int:pk>/",
        views.final_invoice_detail,
        name="final_invoice_detail",
    ),
    path(
        "invoicing/final/<int:pk>/sign/",
        views.final_invoice_sign,
        name="final_invoice_sign",
    ),
    path(
        "invoicing/final/<int:pk>/update/",
        views.final_invoice_update,
        name="final_invoice_update",
    ),
    path(
        "invoicing/final/<int:pk>/pdf/",
        views.final_invoice_pdf,
        name="final_invoice_pdf",
    ),
    path(
        "invoicing/final/<int:pk>/html-preview/",
        views.final_invoice_html_preview,
        name="final_invoice_html_preview",
    ),
    path(
        "invoicing/final/<int:pk>/generate-po/",
        views.final_invoice_generate_purchase_order,
        name="final_invoice_generate_purchase_order",
    ),
    path(
        "invoicing/purchase-orders/",
        views.purchase_order_list,
        name="purchase_order_list",
    ),
    path(
        "invoicing/purchase-orders/<int:pk>/split/",
        views.purchase_order_split_create,
        name="purchase_order_split_create",
    ),
    path(
        "invoicing/purchase-orders/<int:pk>/update/",
        views.purchase_order_update,
        name="purchase_order_update",
    ),
    path(
        "invoicing/purchase-orders/<int:pk>/",
        views.purchase_order_detail,
        name="purchase_order_detail",
    ),
    path(
        "invoicing/purchase-orders/<int:po_pk>/supplier-payments/record/",
        views.record_supplier_payment,
        name="record_supplier_payment",
    ),
    path(
        "invoicing/supplier-payments/",
        views.supplier_payment_list,
        name="supplier_payment_list",
    ),
    path(
        "invoicing/supplier-payments/<int:pk>/delete/",
        views.supplier_payment_delete,
        name="supplier_payment_delete",
    ),
    path("containers/", views.container_return_list, name="container_return_list"),
    path(
        "containers/create/",
        views.container_return_create,
        name="container_return_create",
    ),
    path(
        "containers/<int:pk>/update/",
        views.container_return_update,
        name="container_return_update",
    ),
    # Reports & Exports
    path("reports/", views.reports_dashboard, name="reports_dashboard"),
    path(
        "reports/director/summary/",
        views.director_finance_summary,
        name="director_finance_summary",
    ),
    path("export/clients/", views.export_clients_csv, name="export_clients_csv"),
    path("export/clients/pdf/", views.export_clients_pdf, name="export_clients_pdf"),
    path(
        "export/trade-transactions/",
        views.export_transactions_csv,
        name="export_transactions_csv",
    ),
    path(
        "export/trade-transactions/pdf/",
        views.export_transactions_pdf,
        name="export_transactions_pdf",
    ),
    path("export/sourcing/", views.export_sourcing_csv, name="export_sourcing_csv"),
    path("export/sourcing/pdf/", views.export_sourcing_pdf, name="export_sourcing_pdf"),
    path("export/proformas/", views.export_proformas_csv, name="export_proformas_csv"),
    path(
        "export/proformas/pdf/",
        views.export_proformas_pdf,
        name="export_proformas_pdf",
    ),
    path(
        "export/final-invoices/",
        views.export_final_invoices_csv,
        name="export_final_invoices_csv",
    ),
    path(
        "export/final-invoices/pdf/",
        views.export_final_invoices_pdf,
        name="export_final_invoices_pdf",
    ),
    path(
        "export/purchase-orders/",
        views.export_purchase_orders_csv,
        name="export_purchase_orders_csv",
    ),
    path(
        "export/purchase-orders/pdf/",
        views.export_purchase_orders_pdf,
        name="export_purchase_orders_pdf",
    ),
    path(
        "export/trade-payments/",
        views.export_trade_payments_csv,
        name="export_trade_payments_csv",
    ),
    path(
        "export/trade-payments/pdf/",
        views.export_trade_payments_pdf,
        name="export_trade_payments_pdf",
    ),
    path("export/shipments/", views.export_shipments_csv, name="export_shipments_csv"),
    path(
        "export/shipments/pdf/", views.export_shipments_pdf, name="export_shipments_pdf"
    ),
    path("export/payments/", views.export_payments_csv, name="export_payments_csv"),
    path("export/payments/pdf/", views.export_payments_pdf, name="export_payments_pdf"),
    path(
        "export/containers/", views.export_containers_csv, name="export_containers_csv"
    ),
    path(
        "export/containers/pdf/",
        views.export_containers_pdf,
        name="export_containers_pdf",
    ),
    # Audit Logs
    path("audit-logs/", views.audit_log_view, name="audit_logs"),
    # Workflow Reference
    path("workflow/", views.workflow_guide, name="workflow_guide"),
    # Receipts
    path("receipts/", views.receipt_list, name="receipt_list"),
    path("receipts/<int:pk>/", views.receipt_detail, name="receipt_detail"),
    path(
        "receipts/<int:pk>/preview/",
        views.receipt_html_preview,
        name="receipt_html_preview",
    ),
    path("receipts/<int:pk>/pdf/", views.receipt_pdf, name="receipt_pdf"),
    path("receipts/<int:pk>/reverse/", views.receipt_reverse, name="receipt_reverse"),
    # Sourcing Payments
    path(
        "sourcing-payments/create/",
        views.sourcing_payment_create,
        name="sourcing_payment_create",
    ),
    path(
        "sourcing-payments/create/<int:transaction_pk>/",
        views.sourcing_payment_create,
        name="sourcing_payment_create_for",
    ),
    path(
        "sourcing-payments/due-info/",
        views.sourcing_payment_due_info,
        name="sourcing_payment_due_info",
    ),
    path(
        "transactions/<int:transaction_pk>/payments/",
        views.sourcing_payment_list,
        name="sourcing_payment_list",
    ),
]
