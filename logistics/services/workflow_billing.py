"""Billing service helpers for workflow-driven charge and invoice generation."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from logistics.models import (
    BillingCharge,
    BillingInvoice,
    BillingInvoiceLine,
    BillingPayment,
    CargoItemWorkflow,
    DomainEvent,
    ShipmentWorkflow,
)


class WorkflowBillingService:
    """Encapsulates billing rules derived from operational events."""

    @staticmethod
    def create_charge(
        *,
        shipment: ShipmentWorkflow,
        cargo_item: CargoItemWorkflow | None,
        charge_type: str,
        trigger_event: str,
        idempotency_key: str,
        quantity: Decimal,
        unit_price: Decimal,
        event: DomainEvent | None = None,
    ) -> BillingCharge:
        charge, _ = BillingCharge.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "shipment": shipment,
                "cargo_item": cargo_item,
                "charge_type": charge_type,
                "trigger_event": trigger_event,
                "quantity": quantity,
                "unit_price": unit_price,
                "event": event,
            },
        )
        return charge

    @staticmethod
    def auto_generate_operational_charges(
        *,
        shipment: ShipmentWorkflow,
        cargo_item: CargoItemWorkflow,
        trigger_event: str,
        event_idempotency_key: str,
        event: DomainEvent | None = None,
    ):
        """Emit charge lines from state changes with idempotent keys."""
        if shipment.mode == "LCL" and trigger_event == "CARGO_LOADED":
            WorkflowBillingService.create_charge(
                shipment=shipment,
                cargo_item=cargo_item,
                charge_type="LCL_FREIGHT",
                trigger_event=trigger_event,
                idempotency_key=f"{event_idempotency_key}:LCL_FREIGHT",
                quantity=Decimal(str(cargo_item.chargeable_weight_kg or 0)),
                unit_price=Decimal(str(shipment.lcl_rate_per_kg or 0)),
                event=event,
            )

        if shipment.mode == "FCL" and trigger_event == "SHIPMENT_LOADED":
            WorkflowBillingService.create_charge(
                shipment=shipment,
                cargo_item=None,
                charge_type="FCL_FLAT",
                trigger_event=trigger_event,
                idempotency_key=f"{event_idempotency_key}:FCL_FLAT",
                quantity=Decimal("1"),
                unit_price=Decimal(str(shipment.fcl_flat_rate or 0)),
                event=event,
            )

        if trigger_event == "CARGO_ALLOCATED":
            WorkflowBillingService.create_charge(
                shipment=shipment,
                cargo_item=cargo_item,
                charge_type="HANDLING",
                trigger_event=trigger_event,
                idempotency_key=f"{event_idempotency_key}:HANDLING",
                quantity=Decimal("1"),
                unit_price=Decimal(str(shipment.handling_fee or 0)),
                event=event,
            )

    @staticmethod
    @transaction.atomic
    def issue_invoice_for_shipment(shipment: ShipmentWorkflow) -> BillingInvoice:
        """Create or refresh an invoice from all open charges for a shipment."""
        invoice = (
            BillingInvoice.objects.select_for_update()
            .filter(shipment=shipment, status__in=["DRAFT", "ISSUED", "PARTIALLY_PAID"])
            .order_by("-created_at")
            .first()
        )
        if not invoice:
            invoice = BillingInvoice.objects.create(
                shipment=shipment,
                client=shipment.client,
                status="DRAFT",
            )

        open_charges = BillingCharge.objects.filter(shipment=shipment, status="OPEN")
        for charge in open_charges:
            BillingInvoiceLine.objects.get_or_create(
                invoice=invoice,
                charge=charge,
                defaults={
                    "description": charge.get_charge_type_display(),
                    "quantity": charge.quantity,
                    "unit_price": charge.unit_price,
                    "amount": charge.amount,
                },
            )
            if charge.status != "INVOICED":
                charge.status = "INVOICED"
                charge.save(update_fields=["status"])

        totals = invoice.lines.aggregate(total=Sum("amount"))
        subtotal = totals.get("total") or Decimal("0")
        invoice.subtotal = subtotal
        invoice.tax_amount = Decimal("0")
        invoice.total_amount = subtotal
        if invoice.status == "DRAFT":
            invoice.status = "ISSUED"
            invoice.issued_at = timezone.now()
        invoice.save()
        return invoice

    @staticmethod
    @transaction.atomic
    def register_payment(
        *,
        invoice: BillingInvoice,
        amount: Decimal,
        method: str,
        idempotency_key: str,
        reference: str = "",
        created_by=None,
    ) -> BillingPayment:
        payment, created = BillingPayment.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "invoice": invoice,
                "amount": amount,
                "method": method,
                "reference": reference,
                "created_by": created_by,
            },
        )
        if created:
            invoice.amount_paid = (invoice.amount_paid or Decimal("0")) + payment.amount
            invoice.save()
        return payment
