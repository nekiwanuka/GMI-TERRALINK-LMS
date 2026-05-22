"""
Proof of Delivery (POD) — final close-out artifact for both business lines.

GMI runs two distinct workflows that both end with goods being handed to a
customer:

* **Logistics** — a ``Loading`` arrives in Kampala and is released to the
  consignee.
* **Sourcing / Trading** — a ``FulfillmentOrder`` is delivered to the client
  who placed the original procurement request.

Each ``ProofOfDelivery`` record belongs to exactly one of the two workflows
(enforced by a database CHECK constraint). It captures who received the
goods, when, where, and an attached signature/photo of the signed waybill —
the legal evidence the trade is closed.

Saving a POD also auto-advances the related workflow:

* logistics: links to ``Loading`` and updates the related ``Transit`` status
  to ``arrived`` (if present);
* trading: flips ``FulfillmentOrder.status`` to ``DELIVERED`` and the parent
  ``Transaction.status`` to ``DELIVERED``.

This module lives in its own file as part of the ongoing models package
split (see ``logistics/models/__init__.py``).
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from ._legacy import CustomUser, FulfillmentOrder, Loading, Transaction, Transit


class ProofOfDelivery(models.Model):
    """Legal close-out record for a delivered Loading or FulfillmentOrder."""

    SIDE_LOGISTICS = "logistics"
    SIDE_TRADING = "trading"

    pod_number = models.CharField(max_length=30, unique=True, editable=False)
    loading = models.OneToOneField(
        Loading,
        on_delete=models.PROTECT,
        related_name="proof_of_delivery",
        null=True,
        blank=True,
        help_text="Set when the POD closes a logistics shipment.",
    )
    fulfillment_order = models.OneToOneField(
        FulfillmentOrder,
        on_delete=models.PROTECT,
        related_name="proof_of_delivery",
        null=True,
        blank=True,
        help_text="Set when the POD closes a sourcing / trading delivery.",
    )

    delivered_at = models.DateTimeField(default=timezone.now)
    received_by_name = models.CharField(
        max_length=255,
        help_text="Name of the person who physically received the goods.",
    )
    received_by_phone = models.CharField(max_length=40, blank=True)
    delivery_address = models.CharField(
        max_length=255,
        blank=True,
        help_text="Free-text place name (warehouse, office, site, etc.).",
    )
    signature_or_photo = models.FileField(
        upload_to="pod/",
        blank=True,
        null=True,
        help_text="Photo of the signed delivery note, ID, or signature image.",
    )
    gps_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    gps_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name="proofs_of_delivery",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-delivered_at", "-created_at"]
        verbose_name = "Proof of Delivery"
        verbose_name_plural = "Proofs of Delivery"
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(loading__isnull=False, fulfillment_order__isnull=True)
                    | Q(loading__isnull=True, fulfillment_order__isnull=False)
                ),
                name="pod_belongs_to_exactly_one_workflow",
            )
        ]

    def __str__(self):
        return f"{self.pod_number} - {self.received_by_name}"

    # ------------------------------------------------------------------ helpers
    @property
    def business_side(self):
        return self.SIDE_LOGISTICS if self.loading_id else self.SIDE_TRADING

    @property
    def target_reference(self):
        if self.loading_id:
            return f"Loading {self.loading.loading_id}"
        if self.fulfillment_order_id:
            return f"Fulfillment {self.fulfillment_order.transaction.transaction_id}"
        return "-"

    @classmethod
    def generate_pod_number(cls):
        now = timezone.now()
        prefix = f"POD-{now.strftime('%y%m')}-"
        existing = cls.objects.filter(pod_number__startswith=prefix).values_list(
            "pod_number", flat=True
        )
        next_counter = 1
        for value in existing:
            try:
                counter = int(str(value).split("-")[-1])
                next_counter = max(next_counter, counter + 1)
            except (TypeError, ValueError):
                continue
        return f"{prefix}{next_counter:04d}"

    # --------------------------------------------------------- validation/save
    def clean(self):
        super().clean()
        # Defence in depth — DB constraint already enforces this, but raising
        # a friendly ValidationError makes ModelForm validation cleaner.
        has_loading = bool(self.loading_id)
        has_fulfillment = bool(self.fulfillment_order_id)
        if has_loading == has_fulfillment:
            raise ValidationError(
                "A Proof of Delivery must reference either a Loading or a "
                "Fulfillment Order, but not both."
            )

    def save(self, *args, **kwargs):
        if not self.pod_number:
            self.pod_number = self.generate_pod_number()
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self._advance_related_workflow()

    # ---------------------------------------------------------------- internals
    def _advance_related_workflow(self):
        """Push the linked workflow to its terminal delivered state."""
        if self.loading_id:
            # Logistics — flip the related transit (if any) to "arrived".
            transit = Transit.objects.filter(loading_id=self.loading_id).first()
            if transit and transit.status != "arrived":
                Transit.objects.filter(pk=transit.pk).update(
                    status="arrived", updated_at=timezone.now()
                )
        elif self.fulfillment_order_id:
            FulfillmentOrder.objects.filter(pk=self.fulfillment_order_id).update(
                status="DELIVERED",
                actual_delivery_date=self.delivered_at.date(),
                updated_at=timezone.now(),
            )
            Transaction.objects.filter(pk=self.fulfillment_order.transaction_id).update(
                status="DELIVERED"
            )
