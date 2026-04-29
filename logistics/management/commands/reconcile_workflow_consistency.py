"""Detect and optionally fix inconsistencies across workflow, inventory, and billing."""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from logistics.models import BillingInvoice, CargoItemWorkflow, InventoryPosition


class Command(BaseCommand):
    help = "Reconcile workflow inventory and billing consistency checks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Automatically apply safe invoice and cargo status fixes.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        apply_fix = options["fix"]
        issues = 0

        self.stdout.write("Checking cargo vs inventory positions ...")
        for cargo in CargoItemWorkflow.objects.select_related(
            "inventory_position"
        ).all():
            if not hasattr(cargo, "inventory_position"):
                issues += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Missing InventoryPosition for {cargo.cargo_number}"
                    )
                )
                continue

            pos = cargo.inventory_position
            tracked_total = (
                pos.qty_warehouse
                + pos.qty_reserved
                + pos.qty_in_transit
                + pos.qty_delivered
            )
            if tracked_total != cargo.quantity_total:
                issues += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Balance mismatch {cargo.cargo_number}: tracked={tracked_total} expected={cargo.quantity_total}"
                    )
                )

            if (
                cargo.status == "DELIVERED"
                and pos.qty_delivered != cargo.quantity_total
            ):
                issues += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Delivered mismatch {cargo.cargo_number}: delivered={pos.qty_delivered} expected={cargo.quantity_total}"
                    )
                )
                if apply_fix:
                    cargo.quantity_delivered = cargo.quantity_total
                    cargo.save(update_fields=["quantity_delivered", "updated_at"])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Fixed delivered quantity for {cargo.cargo_number}"
                        )
                    )

        self.stdout.write("Checking invoice totals ...")
        for invoice in BillingInvoice.objects.prefetch_related("lines").all():
            line_sum = invoice.lines.aggregate(total=Sum("amount")).get(
                "total"
            ) or Decimal("0")
            if invoice.subtotal != line_sum or invoice.total_amount != (
                line_sum + invoice.tax_amount
            ):
                issues += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Invoice mismatch {invoice.invoice_number}: subtotal={invoice.subtotal}, line_sum={line_sum}, total={invoice.total_amount}"
                    )
                )
                if apply_fix:
                    invoice.subtotal = line_sum
                    invoice.total_amount = line_sum + invoice.tax_amount
                    invoice.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Fixed invoice totals for {invoice.invoice_number}"
                        )
                    )

        if issues == 0:
            self.stdout.write(self.style.SUCCESS("No consistency issues detected."))
        else:
            self.stdout.write(self.style.WARNING(f"Detected {issues} issue(s)."))
            if not apply_fix:
                self.stdout.write("Run with --fix to apply safe corrections.")
