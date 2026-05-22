"""State-machine services for shipment and cargo transitions with side effects."""

from decimal import Decimal
import uuid

from django.db import transaction
from django.utils import timezone

from logistics.models import (
    CargoItemWorkflow,
    DomainEvent,
    InventoryMovement,
    InventoryPosition,
    ShipmentWorkflow,
    WorkflowTransitionLog,
)
from logistics.services.workflow_billing import WorkflowBillingService


SHIPMENT_TRANSITIONS = {
    "RECEIVED": {"VERIFIED", "CANCELLED"},
    "VERIFIED": {"ALLOCATED", "CANCELLED"},
    "ALLOCATED": {"LOADED", "CANCELLED"},
    "LOADED": {"IN_TRANSIT"},
    "IN_TRANSIT": {"ARRIVED"},
    "ARRIVED": {"DELIVERED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
}

CARGO_TRANSITIONS = {
    "RECEIVED": {"VERIFIED", "CANCELLED"},
    "VERIFIED": {"ALLOCATED", "CANCELLED"},
    "ALLOCATED": {"LOADED", "VERIFIED", "CANCELLED"},
    "LOADED": {"IN_TRANSIT"},
    "IN_TRANSIT": {"ARRIVED"},
    "ARRIVED": {"PARTIALLY_DELIVERED", "DELIVERED"},
    "PARTIALLY_DELIVERED": {"PARTIALLY_DELIVERED", "DELIVERED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
}


class WorkflowTransitionError(Exception):
    pass


def _ensure_transition(allowed_map: dict, from_status: str, to_status: str):
    allowed = allowed_map.get(from_status, set())
    if to_status not in allowed:
        raise WorkflowTransitionError(
            f"Invalid transition: {from_status} -> {to_status}. Allowed: {sorted(allowed)}"
        )


def _make_event(
    *,
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    actor,
    notes: str,
    idempotency_key: str,
):
    event, _ = DomainEvent.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "event_type": event_type,
            "payload": {"notes": notes, "event_type": event_type},
            "created_by": actor,
        },
    )
    return event


def _log_transition(
    *,
    entity_type: str,
    entity_id: int,
    from_status: str,
    to_status: str,
    notes: str,
    actor,
    event,
):
    WorkflowTransitionLog.objects.create(
        entity_type=entity_type,
        entity_id=entity_id,
        from_status=from_status,
        to_status=to_status,
        notes=notes,
        created_by=actor,
        event=event,
    )


def _apply_inventory_movement(
    *,
    cargo_item: CargoItemWorkflow,
    movement_type: str,
    quantity: Decimal,
    from_state: str,
    to_state: str,
    actor,
    event,
    idempotency_key: str,
):
    position, _ = InventoryPosition.objects.select_for_update().get_or_create(
        cargo_item=cargo_item,
        defaults={
            "qty_warehouse": cargo_item.quantity_total,
            "qty_reserved": Decimal("0"),
            "qty_in_transit": Decimal("0"),
            "qty_delivered": Decimal("0"),
        },
    )

    if InventoryMovement.objects.filter(idempotency_key=idempotency_key).exists():
        return

    if movement_type == "RESERVED":
        position.qty_warehouse -= quantity
        position.qty_reserved += quantity
    elif movement_type == "RELEASED":
        position.qty_reserved -= quantity
        position.qty_warehouse += quantity
    elif movement_type == "LOADED":
        position.qty_reserved -= quantity
        position.qty_in_transit += quantity
    elif movement_type == "DELIVERED":
        position.qty_in_transit -= quantity
        position.qty_delivered += quantity

    if (
        min(
            position.qty_warehouse,
            position.qty_reserved,
            position.qty_in_transit,
            position.qty_delivered,
        )
        < 0
    ):
        raise WorkflowTransitionError(
            "Inventory movement would create negative balances."
        )

    position.version += 1
    position.save()

    InventoryMovement.objects.create(
        position=position,
        cargo_item=cargo_item,
        shipment=cargo_item.shipment,
        movement_type=movement_type,
        quantity=quantity,
        from_state=from_state,
        to_state=to_state,
        idempotency_key=idempotency_key,
        created_by=actor,
        event=event,
        metadata={"cargo_status": cargo_item.status},
    )


def _sync_shipment_status_from_cargo(shipment: ShipmentWorkflow):
    statuses = set(shipment.cargo_items.values_list("status", flat=True))
    if not statuses:
        return

    if statuses == {"DELIVERED"}:
        shipment.status = "DELIVERED"
    elif statuses.issubset({"DELIVERED", "PARTIALLY_DELIVERED"}):
        shipment.status = "ARRIVED"
    elif "IN_TRANSIT" in statuses or "ARRIVED" in statuses:
        shipment.status = "IN_TRANSIT"
    elif "LOADED" in statuses:
        shipment.status = "LOADED"
    elif "ALLOCATED" in statuses:
        shipment.status = "ALLOCATED"
    elif "VERIFIED" in statuses:
        shipment.status = "VERIFIED"
    else:
        shipment.status = "RECEIVED"
    shipment.save(update_fields=["status", "updated_at"])


def transition_shipment(
    *,
    shipment: ShipmentWorkflow,
    to_status: str,
    actor=None,
    notes: str = "",
    idempotency_key: str | None = None,
):
    from_status = shipment.status
    _ensure_transition(SHIPMENT_TRANSITIONS, from_status, to_status)

    event_key = (
        idempotency_key
        or f"shipment:{shipment.id}:{from_status}:{to_status}:{uuid.uuid4()}"
    )
    with transaction.atomic():
        locked = ShipmentWorkflow.objects.select_for_update().get(pk=shipment.pk)
        _ensure_transition(SHIPMENT_TRANSITIONS, locked.status, to_status)
        event = _make_event(
            aggregate_type="ShipmentWorkflow",
            aggregate_id=str(locked.pk),
            event_type=f"SHIPMENT_{to_status}",
            actor=actor,
            notes=notes,
            idempotency_key=event_key,
        )

        locked.status = to_status
        locked.save(update_fields=["status", "updated_at"])
        _log_transition(
            entity_type="SHIPMENT",
            entity_id=locked.pk,
            from_status=from_status,
            to_status=to_status,
            notes=notes,
            actor=actor,
            event=event,
        )

        if to_status == "LOADED" and locked.mode == "FCL":
            first_cargo = locked.cargo_items.order_by("id").first()
            if first_cargo:
                WorkflowBillingService.auto_generate_operational_charges(
                    shipment=locked,
                    cargo_item=first_cargo,
                    trigger_event="SHIPMENT_LOADED",
                    event_idempotency_key=event.idempotency_key,
                    event=event,
                )

        if to_status == "DELIVERED":
            WorkflowBillingService.issue_invoice_for_shipment(locked)

        return locked


def transition_cargo_item(
    *,
    cargo_item: CargoItemWorkflow,
    to_status: str,
    actor=None,
    notes: str = "",
    delivered_quantity: Decimal | None = None,
    idempotency_key: str | None = None,
):
    from_status = cargo_item.status
    _ensure_transition(CARGO_TRANSITIONS, from_status, to_status)

    event_key = (
        idempotency_key
        or f"cargo:{cargo_item.id}:{from_status}:{to_status}:{uuid.uuid4()}"
    )

    with transaction.atomic():
        locked = (
            CargoItemWorkflow.objects.select_for_update()
            .select_related("shipment")
            .get(pk=cargo_item.pk)
        )
        _ensure_transition(CARGO_TRANSITIONS, locked.status, to_status)

        event = _make_event(
            aggregate_type="CargoItemWorkflow",
            aggregate_id=str(locked.pk),
            event_type=f"CARGO_{to_status}",
            actor=actor,
            notes=notes,
            idempotency_key=event_key,
        )

        if to_status == "ALLOCATED":
            _apply_inventory_movement(
                cargo_item=locked,
                movement_type="RESERVED",
                quantity=Decimal(str(locked.quantity_total)),
                from_state=locked.inventory_state,
                to_state="RESERVED",
                actor=actor,
                event=event,
                idempotency_key=f"{event_key}:INV:RESERVED",
            )
            locked.inventory_state = "RESERVED"
            WorkflowBillingService.auto_generate_operational_charges(
                shipment=locked.shipment,
                cargo_item=locked,
                trigger_event="CARGO_ALLOCATED",
                event_idempotency_key=event_key,
                event=event,
            )

        elif to_status == "LOADED":
            _apply_inventory_movement(
                cargo_item=locked,
                movement_type="LOADED",
                quantity=Decimal(str(locked.quantity_total)),
                from_state=locked.inventory_state,
                to_state="IN_TRANSIT",
                actor=actor,
                event=event,
                idempotency_key=f"{event_key}:INV:LOADED",
            )
            locked.inventory_state = "IN_TRANSIT"
            WorkflowBillingService.auto_generate_operational_charges(
                shipment=locked.shipment,
                cargo_item=locked,
                trigger_event="CARGO_LOADED",
                event_idempotency_key=event_key,
                event=event,
            )

        elif to_status in {"PARTIALLY_DELIVERED", "DELIVERED"}:
            remaining = Decimal(str(locked.quantity_total)) - Decimal(
                str(locked.quantity_delivered)
            )
            if remaining <= 0:
                raise WorkflowTransitionError("Cargo item is already fully delivered.")

            qty = Decimal(str(delivered_quantity)) if delivered_quantity else remaining
            if qty <= 0 or qty > remaining:
                raise WorkflowTransitionError("Delivered quantity is invalid.")

            _apply_inventory_movement(
                cargo_item=locked,
                movement_type="DELIVERED",
                quantity=qty,
                from_state=locked.inventory_state,
                to_state="DELIVERED" if qty == remaining else "IN_TRANSIT",
                actor=actor,
                event=event,
                idempotency_key=f"{event_key}:INV:DELIVERED:{qty}",
            )
            locked.quantity_delivered = Decimal(str(locked.quantity_delivered)) + qty
            if locked.quantity_delivered >= locked.quantity_total:
                locked.status = "DELIVERED"
                locked.inventory_state = "DELIVERED"
            else:
                locked.status = "PARTIALLY_DELIVERED"
                locked.inventory_state = "IN_TRANSIT"

        if to_status not in {"PARTIALLY_DELIVERED", "DELIVERED"}:
            locked.status = to_status

        locked.save()
        _log_transition(
            entity_type="CARGO",
            entity_id=locked.pk,
            from_status=from_status,
            to_status=locked.status,
            notes=notes,
            actor=actor,
            event=event,
        )

        _sync_shipment_status_from_cargo(locked.shipment)

        if locked.status == "DELIVERED":
            WorkflowBillingService.issue_invoice_for_shipment(locked.shipment)

        return locked
