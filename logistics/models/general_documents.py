from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def _next_document_number(model, field_name, prefix):
    now = timezone.now()
    full_prefix = f"{prefix}-{now.year}{now.month:02d}-"
    latest = (
        model.objects.filter(**{f"{field_name}__startswith": full_prefix})
        .order_by(f"-{field_name}")
        .first()
    )
    next_counter = 1
    if latest:
        try:
            next_counter = int(str(getattr(latest, field_name)).split("-")[-1]) + 1
        except (TypeError, ValueError, IndexError):
            next_counter = model.objects.filter(
                **{f"{field_name}__startswith": full_prefix}
            ).count() + 1
    return f"{full_prefix}{next_counter:04d}"


class GeneralDocumentMixin(models.Model):
    PURPOSE_CHOICES = (
        ("SERVICE", "Service"),
        ("CONSULTATION", "Consultation"),
        ("CLEARING", "Clearing"),
        ("SHIPPING", "Shipping"),
        ("STORAGE", "Storage"),
        ("DOCUMENTATION", "Documentation"),
        ("ADJUSTMENT", "Adjustment"),
        ("OTHER", "Other"),
    )

    client = models.ForeignKey(
        "logistics.Client", on_delete=models.PROTECT, related_name="%(class)ss"
    )
    transaction = models.ForeignKey(
        "logistics.Transaction",
        on_delete=models.PROTECT,
        related_name="%(class)ss",
        null=True,
        blank=True,
    )
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default="SERVICE")
    custom_purpose = models.CharField(max_length=255, blank=True)
    items = models.JSONField(default=list, blank=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="USD")
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "logistics.CustomUser", on_delete=models.PROTECT, related_name="created_%(class)ss"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    @property
    def purpose_label(self):
        if self.purpose == "OTHER" and self.custom_purpose:
            return self.custom_purpose
        return dict(self.PURPOSE_CHOICES).get(self.purpose, self.purpose)

    def calculate_total(self):
        subtotal = Decimal(str(self.subtotal or "0.00"))
        tax_amount = Decimal(str(self.tax_amount or "0.00"))
        discount_amount = Decimal(str(self.discount_amount or "0.00"))
        return max(subtotal + tax_amount - discount_amount, Decimal("0.00"))


class GeneralQuotation(GeneralDocumentMixin):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("SENT", "Sent"),
        ("ACCEPTED", "Accepted"),
        ("CONVERTED", "Converted"),
        ("VOID", "Void"),
    )

    quotation_number = models.CharField(max_length=32, unique=True, editable=False)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="DRAFT")
    valid_until = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.quotation_number

    @classmethod
    def generate_quotation_number(cls):
        return _next_document_number(cls, "quotation_number", "GQ")

    def save(self, *args, **kwargs):
        if not self.quotation_number:
            self.quotation_number = self.generate_quotation_number()
        self.total_amount = self.calculate_total()
        super().save(*args, **kwargs)


class GeneralInvoice(GeneralDocumentMixin):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("ISSUED", "Issued"),
        ("PARTIALLY_PAID", "Partially Paid"),
        ("PAID", "Paid"),
        ("VOID", "Void"),
    )

    invoice_number = models.CharField(max_length=32, unique=True, editable=False)
    quotation = models.ForeignKey(
        GeneralQuotation,
        on_delete=models.PROTECT,
        related_name="general_invoices",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    due_date = models.DateField(null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.invoice_number

    @classmethod
    def generate_invoice_number(cls):
        return _next_document_number(cls, "invoice_number", "GI")

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        self.total_amount = self.calculate_total()
        self.amount_paid = self.payments.aggregate(total=models.Sum("amount"))["total"] or Decimal("0.00") if self.pk else Decimal(str(self.amount_paid or "0.00"))
        self.balance = max(self.total_amount - self.amount_paid, Decimal("0.00"))
        if self.status != "VOID":
            if self.total_amount > 0 and self.balance <= 0:
                self.status = "PAID"
            elif self.amount_paid > 0:
                self.status = "PARTIALLY_PAID"
            elif self.status == "PAID":
                self.status = "ISSUED"
        super().save(*args, **kwargs)


class GeneralPayment(models.Model):
    METHOD_CHOICES = (
        ("CASH", "Cash"),
        ("BANK_TRANSFER", "Bank Transfer"),
        ("MOBILE_MONEY", "Mobile Money"),
        ("CHEQUE", "Cheque"),
        ("OTHER", "Other"),
    )

    invoice = models.ForeignKey(
        GeneralInvoice, on_delete=models.PROTECT, related_name="payments"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="CASH")
    reference = models.CharField(max_length=120, blank=True)
    proof_of_payment = models.FileField(
        upload_to="payments/proofs/general/", blank=True, null=True
    )
    paid_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "logistics.CustomUser", on_delete=models.PROTECT, related_name="general_payments"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at", "-id"]

    def __str__(self):
        return f"{self.amount} {self.currency} for {self.invoice.invoice_number}"

    def clean(self):
        if self.amount is None or self.amount <= 0:
            raise ValidationError({"amount": "Payment amount must be greater than zero."})
        if self.invoice_id:
            balance = self.invoice.balance or Decimal("0.00")
            if self.pk:
                original = GeneralPayment.objects.filter(pk=self.pk).first()
                if original:
                    balance += original.amount
            if self.amount > balance:
                raise ValidationError(
                    {"amount": f"Payment cannot exceed the invoice balance of {balance}."}
                )

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.currency and self.invoice_id:
            self.currency = self.invoice.currency
        self.full_clean()
        super().save(*args, **kwargs)
        self.invoice.save(update_fields=["amount_paid", "balance", "status", "total_amount", "updated_at"])
        if is_new:
            GeneralReceipt.objects.get_or_create(
                payment=self,
                defaults={
                    "amount": self.amount,
                    "currency": self.currency,
                    "issued_to": self.invoice.client.name,
                    "purpose": self.invoice.purpose_label,
                },
            )


class GeneralReceipt(models.Model):
    payment = models.OneToOneField(
        GeneralPayment, on_delete=models.PROTECT, related_name="receipt"
    )
    receipt_number = models.CharField(max_length=32, unique=True, editable=False)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    issued_to = models.CharField(max_length=255)
    purpose = models.CharField(max_length=255, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return self.receipt_number

    @classmethod
    def generate_receipt_number(cls):
        return _next_document_number(cls, "receipt_number", "GR")

    def save(self, *args, **kwargs):
        if self.pk:
            original = GeneralReceipt.objects.filter(pk=self.pk).first()
            if original:
                locked_fields = (
                    "payment_id",
                    "receipt_number",
                    "amount",
                    "currency",
                    "issued_to",
                    "purpose",
                )
                for field in locked_fields:
                    if getattr(original, field) != getattr(self, field):
                        raise ValidationError(
                            "General receipt records are immutable and cannot be modified."
                        )
        if not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
        super().save(*args, **kwargs)
