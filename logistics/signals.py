"""Lightweight safety signals for initializing workflow inventory state."""

from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver

from logistics.models import CargoItemWorkflow, InventoryMovement, InventoryPosition


@receiver(post_save, sender=CargoItemWorkflow)
def initialize_inventory_position(
    sender, instance: CargoItemWorkflow, created, **kwargs
):
    """Initialize inventory records for newly received cargo items (idempotent)."""
    if not created:
        return

    position, _ = InventoryPosition.objects.get_or_create(
        cargo_item=instance,
        defaults={
            "qty_warehouse": Decimal(str(instance.quantity_total)),
            "qty_reserved": Decimal("0"),
            "qty_in_transit": Decimal("0"),
            "qty_delivered": Decimal("0"),
        },
    )

    init_key = f"cargo-init:{instance.pk}:received"
    InventoryMovement.objects.get_or_create(
        idempotency_key=init_key,
        defaults={
            "position": position,
            "cargo_item": instance,
            "shipment": instance.shipment,
            "movement_type": "RECEIVED",
            "quantity": Decimal(str(instance.quantity_total)),
            "from_state": "",
            "to_state": "WAREHOUSE",
            "metadata": {"source": "post_save_init"},
            "created_by": instance.created_by,
        },
    )
