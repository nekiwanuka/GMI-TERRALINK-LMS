"""DRF serializers for workflow transitions and billing operations."""

from rest_framework import serializers

from logistics.models import (
    BillingInvoice,
    BillingPayment,
    CargoItemWorkflow,
    ShipmentWorkflow,
)


class ShipmentWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentWorkflow
        fields = [
            "id",
            "shipment_number",
            "mode",
            "status",
            "client",
            "origin",
            "destination",
            "warehouse_location",
            "created_at",
            "updated_at",
        ]


class CargoItemWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = CargoItemWorkflow
        fields = [
            "id",
            "cargo_number",
            "shipment",
            "description",
            "quantity_total",
            "quantity_delivered",
            "chargeable_weight_kg",
            "status",
            "inventory_state",
            "created_at",
            "updated_at",
        ]


class BillingInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingInvoice
        fields = [
            "id",
            "invoice_number",
            "client",
            "shipment",
            "status",
            "subtotal",
            "tax_amount",
            "total_amount",
            "amount_paid",
            "balance",
            "issued_at",
            "due_date",
            "created_at",
            "updated_at",
        ]


class ShipmentTransitionSerializer(serializers.Serializer):
    to_status = serializers.ChoiceField(choices=ShipmentWorkflow.STATUS_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(required=False, allow_blank=True)


class CargoTransitionSerializer(serializers.Serializer):
    to_status = serializers.ChoiceField(choices=CargoItemWorkflow.STATUS_CHOICES)
    delivered_quantity = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(required=False, allow_blank=True)


class BillingPaymentRegisterSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    method = serializers.ChoiceField(choices=BillingPayment.METHOD_CHOICES)
    reference = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(required=False, allow_blank=True)
