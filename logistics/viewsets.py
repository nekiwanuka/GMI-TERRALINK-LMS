"""DRF ViewSets exposing workflow transitions and payments."""

import uuid

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from logistics.models import BillingInvoice, CargoItemWorkflow, ShipmentWorkflow
from logistics.serializers import (
    BillingInvoiceSerializer,
    BillingPaymentRegisterSerializer,
    CargoItemWorkflowSerializer,
    CargoTransitionSerializer,
    ShipmentTransitionSerializer,
    ShipmentWorkflowSerializer,
)
from logistics.services import (
    WorkflowBillingService,
    WorkflowTransitionError,
    transition_cargo_item,
    transition_shipment,
)


class ShipmentWorkflowViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ShipmentWorkflow.objects.select_related("client").all()
    serializer_class = ShipmentWorkflowSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        shipment = self.get_object()
        serializer = ShipmentTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            updated = transition_shipment(
                shipment=shipment,
                to_status=serializer.validated_data["to_status"],
                actor=request.user,
                notes=serializer.validated_data.get("notes", ""),
                idempotency_key=serializer.validated_data.get("idempotency_key")
                or f"api:shipment:{shipment.pk}:{uuid.uuid4()}",
            )
        except WorkflowTransitionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ShipmentWorkflowSerializer(updated).data)


class CargoItemWorkflowViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CargoItemWorkflow.objects.select_related("shipment").all()
    serializer_class = CargoItemWorkflowSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        cargo_item = self.get_object()
        serializer = CargoTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            updated = transition_cargo_item(
                cargo_item=cargo_item,
                to_status=serializer.validated_data["to_status"],
                actor=request.user,
                notes=serializer.validated_data.get("notes", ""),
                delivered_quantity=serializer.validated_data.get("delivered_quantity"),
                idempotency_key=serializer.validated_data.get("idempotency_key")
                or f"api:cargo:{cargo_item.pk}:{uuid.uuid4()}",
            )
        except WorkflowTransitionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(CargoItemWorkflowSerializer(updated).data)


class BillingInvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BillingInvoice.objects.select_related("shipment", "client").all()
    serializer_class = BillingInvoiceSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["post"])
    def register_payment(self, request, pk=None):
        invoice = self.get_object()
        serializer = BillingPaymentRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payment = WorkflowBillingService.register_payment(
            invoice=invoice,
            amount=serializer.validated_data["amount"],
            method=serializer.validated_data["method"],
            idempotency_key=serializer.validated_data.get("idempotency_key")
            or f"api:payment:{invoice.pk}:{uuid.uuid4()}",
            reference=serializer.validated_data.get("reference", ""),
            created_by=request.user,
        )

        invoice.refresh_from_db()
        return Response(
            {
                "payment_id": payment.id,
                "invoice": BillingInvoiceSerializer(invoice).data,
            },
            status=status.HTTP_201_CREATED,
        )
