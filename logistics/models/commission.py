"""
Commission ledger.

Director / System Admin only side-ledger that records commissions earned per
client. Intentionally decoupled from the shipment, fulfillment and billing
state machines — it is read by ``DirectorReportingService.commission_totals``
for executive aggregation, and is not part of the operational workflow.

This module is the first extracted piece of the historical ``models.py``.
The mechanism is:

    1. Define the model here as usual (no ``app_label`` override).
    2. Re-export it from ``logistics.models.__init__`` so existing imports
       (``from logistics.models import Commission``) still resolve.

Because the class still lives in the ``logistics`` app and is re-exported
under the same name, no migration changes are required.
"""

from django.db import models
from django.utils import timezone

from ._legacy import Client, CustomUser


COMMISSION_CURRENCY_CHOICES = (
    ("USD", "USD - US Dollar"),
    ("UGX", "UGX - Ugandan Shilling"),
    ("CNY", "CNY - Chinese Yuan"),
    ("EUR", "EUR - Euro"),
    ("GBP", "GBP - British Pound"),
    ("KES", "KES - Kenyan Shilling"),
)


class Commission(models.Model):
    """Commissions earned per client. Visible only to Director / System Admin."""

    client = models.ForeignKey(
        Client, on_delete=models.PROTECT, related_name="commissions"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(
        max_length=10, choices=COMMISSION_CURRENCY_CHOICES, default="USD"
    )
    date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name="commissions_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = "Commission"
        verbose_name_plural = "Commissions"

    def __str__(self):
        return f"{self.client.name} - {self.amount} {self.currency} ({self.date})"
