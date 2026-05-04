"""
Database models for the logistics management system
"""

from django.db import models
from django.db.models import F, Q, Sum
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import secrets
import string
import uuid

from ..constants import COUNTRY_CHOICES, CONTAINER_SIZE_CHOICES


class CustomUser(AbstractUser):
    """Custom user model with role-based access"""

    ROLE_CHOICES = (
        ("ADMIN", "System Admin"),
        ("DIRECTOR", "Director"),
        ("OFFICE_ADMIN", "Office Admin (Uganda Intake)"),
        ("FINANCE", "Finance Officer"),
        ("PROCUREMENT", "Procurement Officer"),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="OFFICE_ADMIN")
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    def is_superuser_role(self):
        return self.role == "ADMIN"

    def is_data_entry_role(self):
        return self.role == "OFFICE_ADMIN"

    def save(self, *args, **kwargs):
        """Keep role/is_staff aligned with Django's superuser flag."""
        if self.is_superuser:
            self.role = "ADMIN"
            self.is_staff = True
        super().save(*args, **kwargs)

    @property
    def is_admin_role(self):
        return self.role == "ADMIN"

    @property
    def is_director_role(self):
        return self.role == "DIRECTOR"

    @property
    def is_finance_role(self):
        return self.role == "FINANCE"

    @property
    def is_procurement_role(self):
        return self.role == "PROCUREMENT"


class Notification(models.Model):
    """Persistent in-app notification for operational events."""

    CATEGORY_CHOICES = (
        ("document", "Document"),
        ("invoice", "Invoice"),
        ("system", "System"),
    )

    recipient = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="notifications"
    )
    title = models.CharField(max_length=160)
    message = models.TextField()
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default="system"
    )
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
            models.Index(fields=["category", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.title} -> {self.recipient.username}"


def _random_code(length=10):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _random_digits(length=10):
    return "".join(secrets.choice(string.digits) for _ in range(length))


def _draw_standard_doc_header(pdf, width, height, title, reference=""):
    """Draw a unified GMI document header with branch office blocks."""
    from reportlab.lib import colors
    from pathlib import Path

    margin = 40
    primary = colors.HexColor("#1E1A23")
    accent = colors.HexColor("#F4C21F")

    y_top = height - 34
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(margin, y_top, "CHINA BRANCH OFFICE")
    pdf.setFont("Helvetica", 7)
    pdf.drawString(margin, y_top - 12, "B239B (ECAT): +86 177 0195 4464")
    pdf.drawString(
        margin,
        y_top - 22,
        "No.3 Shafeng 3rd Rd, Jinsha B Station 2F, Baiyun, Guangzhou",
    )
    pdf.drawString(margin, y_top - 32, "gmiterralinkinfo@gmail.com")

    logo_path = Path(__file__).resolve().parent.parent.parent / "gmi_logo.png"
    if not logo_path.exists():
        logo_path = (
            Path(__file__).resolve().parent.parent
            / "static"
            / "images"
            / "gmi_logo.png"
        )
    if logo_path.exists():
        logo_plate_x = (width / 2) - 48
        logo_plate_y = y_top - 31
        pdf.setFillColor(colors.white)
        pdf.setStrokeColor(colors.HexColor("#E6E6E6"))
        pdf.roundRect(logo_plate_x, logo_plate_y, 96, 36, 4, fill=1, stroke=1)
        pdf.drawImage(
            str(logo_path),
            (width / 2) - 44,
            y_top - 29,
            width=88,
            height=30,
            preserveAspectRatio=True,
            mask="auto",
        )
    pdf.setFillColor(primary)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(width / 2, y_top - 32, title)
    if reference:
        pdf.setFont("Helvetica", 8)
        pdf.setFillColor(colors.grey)
        pdf.drawCentredString(width / 2, y_top - 44, str(reference))

    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawRightString(width - margin, y_top, "UGANDA BRANCH OFFICE")
    pdf.setFont("Helvetica", 7)
    pdf.drawRightString(width - margin, y_top - 12, "+256 768 049 940")
    pdf.drawRightString(
        width - margin,
        y_top - 22,
        "Hamdeen Lwanga Close, Mitala Rd, Plot 10/12, Muyenga, Kampala",
    )
    pdf.drawRightString(width - margin, y_top - 32, "www.gmi-terralink.com")

    pdf.setFillColor(accent)
    pdf.rect(margin, height - 94, width - (2 * margin), 2, fill=1, stroke=0)


def _draw_international_terms_footer(pdf, margin, y_top=60):
    """Draw a compact international terms block used on generated PDFs."""
    from reportlab.lib import colors

    pdf.setFillColor(colors.grey)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(
        margin,
        y_top,
        "International Terms: Ex-Works unless agreed in writing. Duties, taxes, and bank charges are for buyer account.",
    )
    pdf.drawString(
        margin,
        y_top - 12,
        "Delivery dates are estimates subject to carrier schedules, customs, force majeure, and regulatory controls.",
    )
    pdf.drawString(
        margin,
        y_top - 24,
        "Claims for shortages or damage must be submitted in writing within 3 business days of delivery.",
    )
    pdf.drawString(
        margin,
        y_top - 36,
        "gmiterralinkinfo@gmail.com | +256 768 049 940 | +86 177 0195 4464 | www.gmi-terralink.com",
    )
    pdf.drawString(
        margin,
        y_top - 48,
        "Services: Procurement | Sea & Air Logistics | Mining & Equipment | Translation | Money Transfer",
    )


class Client(models.Model):
    """Client management model"""

    client_id = models.CharField(max_length=50, unique=True, editable=False)
    name = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255, blank=True)
    contact_person = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField()
    country = models.CharField(max_length=100, choices=COUNTRY_CHOICES, blank=True)
    date_registered = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="created_clients"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["phone"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.client_id} - {self.name}"

    @classmethod
    def generate_unique_id(cls):
        """Generate a unique client ID prefixed with GTL."""
        while True:
            candidate = f"GTL{_random_digits(5)}"
            if not cls.objects.filter(client_id=candidate).exists():
                return candidate

    def save(self, *args, **kwargs):
        if not self.client_id:
            self.client_id = self.generate_unique_id()
        super().save(*args, **kwargs)


class Loading(models.Model):
    """Cargo/Loading management model"""

    ENTRY_TYPE_CHOICES = (
        ("FULL_CONTAINER", "Full Container"),
        ("GROUPAGE", "Groupage"),
    )

    loading_id = models.CharField(max_length=50, unique=True)
    entry_type = models.CharField(
        max_length=20, choices=ENTRY_TYPE_CHOICES, default="FULL_CONTAINER"
    )
    client = models.ForeignKey(
        Client, on_delete=models.PROTECT, related_name="loadings"
    )
    loading_date = models.DateTimeField()
    item_description = models.TextField()
    packages = models.PositiveIntegerField(null=True, blank=True)
    weight = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )  # in KG
    cbm = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    container_number = models.CharField(max_length=100, blank=True)
    container_size = models.CharField(
        max_length=20, choices=CONTAINER_SIZE_CHOICES, blank=True
    )
    warehouse_location = models.CharField(max_length=255, blank=True)
    bill_of_lading_number = models.CharField(
        max_length=40, unique=True, blank=True, null=True
    )
    groupage_note_number = models.CharField(
        max_length=40, unique=True, blank=True, null=True
    )
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_loadings",
    )
    closure_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="created_loadings"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entry_type", "closed_at"]),
            models.Index(fields=["client", "-created_at"]),
            models.Index(fields=["origin"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.loading_id} - {self.client.name}"

    @property
    def is_closed(self):
        return self.closed_at is not None

    @classmethod
    def generate_loading_id(cls, entry_type="FULL_CONTAINER"):
        year_short = timezone.now().strftime("%y")
        if entry_type == "FULL_CONTAINER":
            prefix = f"CFC-GMI-UG-{year_short}-"
        else:
            prefix = f"CGP-GMI-UG-{year_short}-"

        next_counter = 1
        existing_ids = cls.objects.filter(loading_id__startswith=prefix).values_list(
            "loading_id", flat=True
        )
        for entry_id in existing_ids:
            try:
                counter = int(str(entry_id).split("-")[-1])
                next_counter = max(next_counter, counter + 1)
            except (TypeError, ValueError):
                continue
        return f"{prefix}{next_counter:02d}"

    @classmethod
    def generate_bill_of_lading_number(cls):
        year_short = timezone.now().strftime("%y")
        prefix = f"BOL-GMI-UG-{year_short}-"
        next_counter = 1
        existing_bols = cls.objects.filter(
            bill_of_lading_number__startswith=prefix
        ).values_list("bill_of_lading_number", flat=True)
        for bol_number in existing_bols:
            try:
                counter = int(str(bol_number).split("-")[-1])
                next_counter = max(next_counter, counter + 1)
            except (TypeError, ValueError):
                continue
        return f"{prefix}{next_counter:02d}"

    @classmethod
    def generate_groupage_note_number(cls):
        year_short = timezone.now().strftime("%y")
        prefix = f"GCN-GMI-UG-{year_short}-"
        next_counter = 1
        existing_notes = cls.objects.filter(
            groupage_note_number__startswith=prefix
        ).values_list("groupage_note_number", flat=True)
        for note_number in existing_notes:
            try:
                counter = int(str(note_number).split("-")[-1])
                next_counter = max(next_counter, counter + 1)
            except (TypeError, ValueError):
                continue
        return f"{prefix}{next_counter:02d}"

    def save(self, *args, **kwargs):
        if not self.loading_id:
            self.loading_id = self.generate_loading_id(self.entry_type)
        if self.entry_type == "FULL_CONTAINER" and not self.bill_of_lading_number:
            self.bill_of_lading_number = self.generate_bill_of_lading_number()
            self.groupage_note_number = None
        if self.entry_type == "GROUPAGE" and not self.groupage_note_number:
            self.groupage_note_number = self.generate_groupage_note_number()
            self.bill_of_lading_number = None
        if self.entry_type != "FULL_CONTAINER":
            self.bill_of_lading_number = None
        if self.entry_type != "GROUPAGE":
            self.groupage_note_number = None
            self.packages = None
            self.cbm = None
        super().save(*args, **kwargs)

    @property
    def chargeable_wm(self):
        """Chargeable W/M for LCL where 1 CBM is treated as 1 metric ton."""
        if self.entry_type != "GROUPAGE":
            return None
        weight_tons = (self.weight / 1000) if self.weight else None
        if weight_tons is None and self.cbm is None:
            return None
        if weight_tons is None:
            return self.cbm
        if self.cbm is None:
            return weight_tons
        return max(weight_tons, self.cbm)


class Transit(models.Model):
    """Transit/Vessel management model"""

    STATUS_CHOICES = (
        ("awaiting", "Awaiting"),
        ("in_transit", "In Transit"),
        ("arrived", "Arrived"),
    )

    loading = models.OneToOneField(
        Loading, on_delete=models.CASCADE, related_name="transit"
    )
    vessel_name = models.CharField(max_length=255)
    boarding_date = models.DateTimeField()
    eta_kampala = models.DateTimeField()  # Estimated Time of Arrival
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="awaiting")
    remarks = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="created_transits"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.vessel_name} - {self.loading.loading_id}"


class Payment(models.Model):
    """Payment management model"""

    PAYMENT_METHOD_CHOICES = (
        ("cash", "Cash"),
        ("bank_transfer", "Bank Transfer"),
        ("cheque", "Cheque"),
        ("other", "Other"),
    )
    BILLING_BASIS_CHOICES = (
        ("manual", "Manual Amount"),
        ("kg", "Weight (KG)"),
        ("cbm", "CBM"),
    )

    loading = models.OneToOneField(
        Loading, on_delete=models.CASCADE, related_name="payment"
    )
    final_invoice = models.ForeignKey(
        "FinalInvoice",
        on_delete=models.PROTECT,
        related_name="logistics_payments",
        null=True,
        blank=True,
    )
    billing_basis = models.CharField(
        max_length=10, choices=BILLING_BASIS_CHOICES, default="manual"
    )
    billing_rate = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    amount_charged = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateTimeField(null=True, blank=True)
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True
    )
    receipt_number = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="created_payments"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment for {self.loading.loading_id}"

    @property
    def invoice_number(self):
        if self.id:
            return f"INV-{self.id:05d}"
        return "INV-DRAFT"

    def refresh_totals(self):
        """Recalculate amount paid/balance from related transactions."""
        total_paid = self.transactions.aggregate(total=Sum("amount"))["total"] or 0
        balance = self.amount_charged - total_paid
        Payment.objects.filter(pk=self.pk).update(
            amount_paid=total_paid, balance=balance, updated_at=timezone.now()
        )
        self.amount_paid = total_paid
        self.balance = balance

    def get_billing_quantity(self):
        if not self.loading or self.loading.entry_type != "GROUPAGE":
            return None
        if self.billing_basis == "kg":
            return self.loading.weight
        if self.billing_basis == "cbm":
            return self.loading.cbm
        return None

    def calculate_amount_charged(self):
        quantity = self.get_billing_quantity()
        if quantity is None or self.billing_rate is None:
            return self.amount_charged
        return (Decimal(quantity) * self.billing_rate).quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        if self.loading and self.loading.entry_type != "GROUPAGE":
            self.billing_basis = "manual"
            self.billing_rate = None
        elif self.loading and self.billing_basis in {"kg", "cbm"}:
            self.amount_charged = self.calculate_amount_charged()
        else:
            self.billing_rate = None
        # Automatically calculate balance
        self.balance = self.amount_charged - self.amount_paid
        super().save(*args, **kwargs)


class PaymentTransaction(models.Model):
    """Individual payment events supporting partial payments."""

    VERIFICATION_CHOICES = (
        ("pending", "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    payment = models.ForeignKey(
        Payment, related_name="transactions", on_delete=models.CASCADE
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateTimeField(default=timezone.now)
    payment_method = models.CharField(
        max_length=20, choices=Payment.PAYMENT_METHOD_CHOICES
    )
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_CHOICES, default="pending"
    )
    verification_notes = models.TextField(blank=True)
    verified_by = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_transactions",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="payment_transactions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-payment_date"]

    def __str__(self):
        return f"{self.receipt_number} - {self.payment.loading.loading_id}"

    @property
    def receipt_number(self):
        if self.id:
            return f"RCT-{self.id:05d}"
        return "RCT-DRAFT"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        self.payment.refresh_totals()
        if is_new:
            # Resolve the client name for the receipt snapshot
            try:
                client_name = self.payment.loading.client.name
            except Exception:
                client_name = "Unknown"
            Receipt.objects.get_or_create(
                logistics_payment=self,
                defaults={
                    "amount": self.amount,
                    "currency": "UGX",
                    "issued_to": client_name,
                },
            )

    def delete(self, *args, **kwargs):
        payment = self.payment
        super().delete(*args, **kwargs)
        payment.refresh_totals()


class ContainerReturn(models.Model):
    """Container return management model"""

    CONDITION_CHOICES = (
        ("good", "Good"),
        ("damaged", "Damaged"),
        ("missing", "Missing"),
    )

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("returned", "Returned"),
        ("damaged_inspected", "Damaged - Inspected"),
    )

    container_number = models.CharField(max_length=100)
    container_size = models.CharField(
        max_length=20, choices=CONTAINER_SIZE_CHOICES, blank=True
    )
    loading = models.ForeignKey(
        Loading, on_delete=models.PROTECT, related_name="container_returns"
    )
    return_date = models.DateTimeField()
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    remarks = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="created_container_returns"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.container_number} - {self.get_status_display()}"


class AuditLog(models.Model):
    """Audit trail for tracking changes"""

    ACTION_CHOICES = (
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
    )

    MODEL_CHOICES = (
        ("client", "Client"),
        ("loading", "Loading"),
        ("transit", "Transit"),
        ("payment", "Payment"),
        ("container_return", "Container Return"),
        ("user", "User"),
    )

    user = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, related_name="audit_logs"
    )
    model_type = models.CharField(max_length=50, choices=MODEL_CHOICES)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    object_id = models.IntegerField()
    object_str = models.CharField(max_length=255)
    changes = models.JSONField(null=True, blank=True)  # Store what changed
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name_plural = "Audit Logs"
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["model_type", "action", "-timestamp"]),
            models.Index(fields=["user", "-timestamp"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} - {self.get_model_type_display()} ({self.object_str})"


class Supplier(models.Model):
    """Supplier contact database."""

    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    supplies = models.TextField(
        blank=True,
        help_text="Products or materials this supplier can provide.",
    )
    min_order_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Minimum quantity accepted per order.",
    )
    reference_unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Typical unit price used for quick comparison.",
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="created_suppliers"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SupplierProduct(models.Model):
    """Product-level catalog entries for each supplier."""

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name="products",
    )
    product_name = models.CharField(max_length=255)
    specifications = models.TextField(
        blank=True,
        help_text="Technical details, grade, size, material, etc.",
    )
    min_order_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Minimum quantity the supplier will accept per order.",
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Supplier's quoted buying/cost price per unit.",
    )
    resale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Suggested client-facing resale price per unit.",
    )
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name="created_supplier_products",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product_name"]

    def __str__(self):
        return f"{self.supplier.name} - {self.product_name}"


class InventoryItem(models.Model):
    """Inventory tracking for purchased and shipped parts."""

    STOCK_STATUS_CHOICES = (
        ("IN_STOCK", "In Stock"),
        ("LOW_STOCK", "Low Stock"),
        ("OUT_OF_STOCK", "Out Of Stock"),
    )

    item_code = models.CharField(max_length=100, unique=True)
    item_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    quantity_purchased = models.PositiveIntegerField(default=0)
    quantity_shipped = models.PositiveIntegerField(default=0)
    quantity_in_warehouse = models.PositiveIntegerField(default=0)
    stock_status = models.CharField(
        max_length=20, choices=STOCK_STATUS_CHOICES, default="IN_STOCK"
    )
    transaction = models.ForeignKey(
        "Transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_items",
        help_text="Owner transaction for this stored stock item.",
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_items",
    )
    updated_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="inventory_updates"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["item_name"]

    def __str__(self):
        return f"{self.item_code} - {self.item_name}"

    @property
    def owner_client(self):
        return self.transaction.customer if self.transaction else None

    @property
    def allocated_quantity(self):
        totals = self.fulfillment_lines.aggregate(
            allocated=Sum("quantity_allocated"),
            dispatched=Sum("quantity_dispatched"),
        )
        return max((totals["allocated"] or 0) - (totals["dispatched"] or 0), 0)

    @property
    def available_quantity(self):
        return max(self.quantity_in_warehouse - self.allocated_quantity, 0)

    def save(self, *args, **kwargs):
        if self.quantity_shipped > self.quantity_purchased:
            raise ValidationError("Shipped quantity cannot exceed purchased quantity.")
        self.quantity_in_warehouse = max(
            self.quantity_purchased - self.quantity_shipped, 0
        )
        if self.quantity_in_warehouse == 0:
            self.stock_status = "OUT_OF_STOCK"
        elif self.quantity_in_warehouse <= 10:
            self.stock_status = "LOW_STOCK"
        else:
            self.stock_status = "IN_STOCK"
        super().save(*args, **kwargs)


class Transaction(models.Model):
    """Core transaction object that ties customer, sourcing, invoices, and shipping."""

    STATUS_CHOICES = (
        ("RECEIVED", "Received"),
        ("CLEANED", "Cleaned"),
        ("SENT_TO_SOURCING", "Sent To Sourcing"),
        ("QUOTED", "Quoted"),
        ("PROFORMA_CREATED", "Proforma Created"),
        ("PROFORMA_SENT", "Proforma Sent"),
        ("CONFIRMED", "Confirmed"),
        ("FINAL_INVOICE_CREATED", "Final Invoice Created"),
        ("PAID", "Paid"),
        ("SHIPPED", "Shipped"),
        ("DELIVERED", "Delivered"),
        ("CLOSED", "Closed"),
    )

    transaction_id = models.CharField(
        "Entry Number", max_length=20, unique=True, editable=False
    )
    source_loading = models.OneToOneField(
        "Loading",
        on_delete=models.PROTECT,
        related_name="source_transaction",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        Client, on_delete=models.PROTECT, related_name="transactions"
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="RECEIVED")
    description = models.TextField(
        blank=True,
        help_text="Brief description of the goods or service being sourced.",
    )
    notes = models.TextField(
        blank=True, help_text="Internal notes for this transaction."
    )
    estimated_delivery = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_transactions",
    )
    closure_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="created_transactions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "closed_at"]),
            models.Index(fields=["customer", "-created_at"]),
            models.Index(fields=["source_loading"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return self.transaction_id

    @property
    def is_closed(self):
        return self.status == "CLOSED" or self.closed_at is not None

    @classmethod
    def generate_transaction_id(cls):
        year_short = timezone.now().strftime("%y")
        prefix = f"GMI-UG-{year_short}-"
        next_counter = 1

        latest_with_prefix = cls.objects.filter(
            transaction_id__startswith=prefix
        ).values_list("transaction_id", flat=True)

        for tx_id in latest_with_prefix:
            try:
                counter = int(str(tx_id).split("-")[-1])
                next_counter = max(next_counter, counter + 1)
            except (TypeError, ValueError):
                continue

        return f"{prefix}{next_counter:02d}"

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = self.generate_transaction_id()
        elif self.pk:
            original = (
                Transaction.objects.filter(pk=self.pk).only("transaction_id").first()
            )
            if original and original.transaction_id != self.transaction_id:
                raise ValidationError(
                    "transaction_id is immutable and cannot be changed."
                )
        super().save(*args, **kwargs)


class FulfillmentOrder(models.Model):
    """Warehouse-to-delivery fulfillment workflow for a transaction."""

    STATUS_CHOICES = (
        ("WAREHOUSE_RECEIVED", "Received In Warehouse"),
        ("ALLOCATED", "Allocated For Shipment"),
        ("DISPATCHED_FROM_WAREHOUSE", "Dispatched From Warehouse"),
        ("AT_PORT", "At Port Of Loading"),
        ("SEA_TRANSIT", "Sea Transit"),
        ("AT_DESTINATION_PORT", "Arrived At Destination Port"),
        ("INLAND_TRANSIT", "Inland Transit"),
        ("DELIVERED", "Delivered"),
    )

    transaction = models.OneToOneField(
        "Transaction", on_delete=models.CASCADE, related_name="fulfillment_order"
    )
    final_invoice = models.ForeignKey(
        "FinalInvoice",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fulfillment_orders",
    )
    requires_warehouse_handling = models.BooleanField(default=False)
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default="WAREHOUSE_RECEIVED",
    )
    warehouse_received_at = models.DateTimeField(null=True, blank=True)
    warehouse_notes = models.TextField(blank=True)
    port_of_loading = models.CharField(max_length=255, blank=True)
    destination_port = models.CharField(max_length=255, blank=True)
    inland_destination = models.CharField(max_length=255, blank=True)
    consignee = models.CharField(max_length=255, blank=True)
    planned_dispatch_date = models.DateField(null=True, blank=True)
    planned_delivery_date = models.DateField(null=True, blank=True)
    actual_delivery_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name="created_fulfillment_orders",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Fulfillment {self.transaction.transaction_id}"

    @property
    def source_reference(self):
        if self.final_invoice_id:
            return f"FI-{self.final_invoice_id}"
        return self.transaction.transaction_id

    @property
    def total_allocated(self):
        return self.lines.aggregate(total=Sum("quantity_allocated"))["total"] or 0

    @property
    def total_dispatched(self):
        return self.lines.aggregate(total=Sum("quantity_dispatched"))["total"] or 0

    @property
    def total_delivered(self):
        return self.lines.aggregate(total=Sum("quantity_delivered"))["total"] or 0

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        next_transaction_status = None
        if self.status == "DELIVERED":
            next_transaction_status = "DELIVERED"
        elif self.status in {
            "DISPATCHED_FROM_WAREHOUSE",
            "AT_PORT",
            "SEA_TRANSIT",
            "AT_DESTINATION_PORT",
            "INLAND_TRANSIT",
        }:
            next_transaction_status = "SHIPPED"

        if (
            next_transaction_status
            and self.transaction.status != next_transaction_status
        ):
            Transaction.objects.filter(pk=self.transaction_id).update(
                status=next_transaction_status
            )

    def clean(self):
        super().clean()
        if (
            self.final_invoice_id
            and self.final_invoice.transaction_id != self.transaction_id
        ):
            raise ValidationError(
                "Selected final invoice must belong to the same transaction."
            )
        if not self.final_invoice_id:
            raise ValidationError(
                {
                    "final_invoice": "Select the final invoice that drives this fulfillment workflow."
                }
            )
        if not self.requires_warehouse_handling:
            self.warehouse_received_at = None


class FulfillmentLine(models.Model):
    """Warehouse allocation and shipment quantities per inventory item."""

    order = models.ForeignKey(
        FulfillmentOrder, on_delete=models.CASCADE, related_name="lines"
    )
    inventory_item = models.ForeignKey(
        InventoryItem, on_delete=models.PROTECT, related_name="fulfillment_lines"
    )
    quantity_allocated = models.PositiveIntegerField(default=0)
    quantity_dispatched = models.PositiveIntegerField(default=0)
    quantity_delivered = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["inventory_item__item_name", "created_at"]

    def __str__(self):
        return f"{self.order} - {self.inventory_item.item_code}"

    def clean(self):
        super().clean()
        if not self.inventory_item_id or not self.order_id:
            return
        if self.inventory_item.transaction_id != self.order.transaction_id:
            raise ValidationError(
                "Allocated warehouse stock must belong to the same transaction."
            )
        if self.quantity_dispatched > self.quantity_allocated:
            raise ValidationError(
                "Dispatched quantity cannot exceed allocated quantity."
            )
        if self.quantity_delivered > self.quantity_dispatched:
            raise ValidationError(
                "Delivered quantity cannot exceed dispatched quantity."
            )

        other_lines = self.inventory_item.fulfillment_lines.exclude(pk=self.pk)
        other_reserved = sum(
            max(line.quantity_allocated - line.quantity_dispatched, 0)
            for line in other_lines
        )
        available_for_reservation = max(
            self.inventory_item.quantity_in_warehouse - other_reserved,
            0,
        )
        current_reserved = max(self.quantity_allocated - self.quantity_dispatched, 0)
        if current_reserved > available_for_reservation:
            raise ValidationError(
                "Allocated quantity exceeds warehouse stock still available for reservation."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        self.sync_inventory_item()

    def delete(self, *args, **kwargs):
        inventory_item = self.inventory_item
        super().delete(*args, **kwargs)
        self.sync_inventory_item(inventory_item=inventory_item)

    def sync_inventory_item(self, inventory_item=None):
        inventory_item = inventory_item or self.inventory_item
        dispatched_total = (
            inventory_item.fulfillment_lines.aggregate(
                total=Sum("quantity_dispatched")
            )["total"]
            or 0
        )
        inventory_item.quantity_shipped = dispatched_total
        inventory_item.save()


class ShipmentLeg(models.Model):
    """A movement leg within a fulfillment order."""

    LEG_TYPE_CHOICES = (
        ("WAREHOUSE_TO_PORT", "Warehouse To Port"),
        ("SEA_FREIGHT", "Sea Freight"),
        ("PORT_TO_DESTINATION", "Port To Destination"),
    )

    STATUS_CHOICES = (
        ("PLANNED", "Planned"),
        ("IN_TRANSIT", "In Transit"),
        ("ARRIVED", "Arrived"),
        ("COMPLETED", "Completed"),
    )

    order = models.ForeignKey(
        FulfillmentOrder, on_delete=models.CASCADE, related_name="legs"
    )
    sequence = models.PositiveIntegerField(default=1)
    leg_type = models.CharField(max_length=24, choices=LEG_TYPE_CHOICES)
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    carrier = models.CharField(max_length=255, blank=True)
    vehicle_or_vessel = models.CharField(max_length=255, blank=True)
    departure_date = models.DateField(null=True, blank=True)
    arrival_eta = models.DateField(null=True, blank=True)
    actual_arrival = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PLANNED")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name="created_shipment_legs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sequence", "created_at"]
        unique_together = (("order", "sequence"),)

    def __str__(self):
        return f"{self.order} - leg {self.sequence}"

    def clean(self):
        super().clean()
        if (
            self.arrival_eta
            and self.departure_date
            and self.arrival_eta < self.departure_date
        ):
            raise ValidationError("Arrival ETA cannot be before departure date.")
        if (
            self.actual_arrival
            and self.departure_date
            and self.actual_arrival < self.departure_date
        ):
            raise ValidationError("Actual arrival cannot be before departure date.")


class Document(models.Model):
    """Stores uploaded inquiry and finance documents per transaction."""

    DOCUMENT_TYPE_CHOICES = (
        ("CLIENT_PI", "Client Purchase Inquiry (PI)"),
        ("INQUIRY", "Inquiry"),
        ("CLEANED", "Cleaned"),
        ("INVOICE", "Invoice"),
        ("RECEIPT", "Receipt"),
    )

    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="documents"
    )
    document_type = models.CharField(
        max_length=20, choices=DOCUMENT_TYPE_CHOICES, default="CLIENT_PI"
    )
    original_file = models.FileField(
        upload_to="transactions/originals/",
        help_text="Accepted: PDF, Word (.docx), or plain text files.",
    )
    processed_file = models.FileField(
        upload_to="transactions/processed/", blank=True, null=True
    )
    extracted_text = models.TextField(
        blank=True,
        help_text="Auto-extracted text content from the uploaded document.",
    )
    structured_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured data parsed from a Client PI document (client name, items, deadline, etc.).",
    )
    uploaded_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="uploaded_documents"
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.transaction.transaction_id} - {self.document_type}"


class DocumentArchive(models.Model):
    """Immutable archive snapshot for uploaded documents with extracted output."""

    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="archives"
    )
    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="document_archives"
    )
    document_type = models.CharField(
        max_length=20,
        choices=Document.DOCUMENT_TYPE_CHOICES,
        default="CLIENT_PI",
    )
    original_filename = models.CharField(max_length=255)
    archived_file = models.FileField(upload_to="transactions/archive/originals/")
    extracted_text = models.TextField(blank=True)
    structured_data = models.JSONField(default=dict, blank=True)
    archived_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="archived_documents"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Archive {self.transaction.transaction_id} - {self.original_filename}"

    @classmethod
    def create_from_document(cls, document, archived_by=None):
        """Persist a file and extraction snapshot for later reference."""
        import os
        from django.core.files.base import ContentFile

        if not document.original_file:
            return None

        archive = cls(
            document=document,
            transaction=document.transaction,
            document_type=document.document_type,
            original_filename=os.path.basename(document.original_file.name or "upload"),
            extracted_text=document.extracted_text or "",
            structured_data=document.structured_data or {},
            archived_by=archived_by or document.uploaded_by,
        )

        document.original_file.open("rb")
        try:
            file_bytes = document.original_file.read()
        finally:
            document.original_file.close()

        archive_name = (
            f"{document.transaction.transaction_id}_"
            f"{timezone.now().strftime('%Y%m%d%H%M%S')}_"
            f"{archive.original_filename}"
        )
        archive.archived_file.save(archive_name, ContentFile(file_bytes), save=False)
        archive.save()
        return archive


class Sourcing(models.Model):
    """Overseas sourcing details attached to transaction."""

    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="sourcing_entries"
    )
    supplier_name = models.CharField(max_length=255)
    supplier_contact = models.CharField(max_length=255, blank=True)
    item_details = models.JSONField(default=list, blank=True)
    unit_prices = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="created_sourcing_records"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Sourcing - {self.transaction.transaction_id}"

    def clean(self):
        allowed_roles = {"PROCUREMENT", "ADMIN"}
        if self.created_by_id and self.created_by.role not in allowed_roles:
            raise ValidationError(
                "Only Procurement Officer can create or update sourcing records."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ProformaInvoice(models.Model):
    """Non-binding quotation invoice linked to a transaction."""

    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("SENT", "Sent"),
    )

    transaction = models.ForeignKey(
        Transaction, on_delete=models.PROTECT, related_name="proforma_invoices"
    )
    loading = models.ForeignKey(
        "Loading",
        on_delete=models.PROTECT,
        related_name="proforma_invoices",
        null=True,
        blank=True,
    )
    items = models.JSONField(default=list)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    sourcing_fee = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    handling_fee = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    shipping_fee = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    validity_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="DRAFT")
    supplier_name = models.CharField(max_length=255, blank=True, default="")
    supplier_address = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="created_proformas"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PI-{self.pk or 'DRAFT'}-{self.transaction.transaction_id}"

    @property
    def total_amount(self):
        return (
            (self.subtotal or Decimal("0.00"))
            + (self.sourcing_fee or Decimal("0.00"))
            + (self.handling_fee or Decimal("0.00"))
            + (self.shipping_fee or Decimal("0.00"))
        )

    def generate_pdf(self):
        from io import BytesIO
        from decimal import Decimal, InvalidOperation
        from pathlib import Path
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        def _fmt(value):
            try:
                return f"{Decimal(str(value or 0)):,.2f}"
            except (InvalidOperation, TypeError, ValueError):
                return "-"

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        W, H = A4
        M = 28
        CW = W - 2 * M

        navy = colors.HexColor("#1A1A1A")
        orange = colors.HexColor("#C9A227")
        black = colors.HexColor("#1F1F1F")
        dark_grey = colors.HexColor("#4E5563")
        mid_grey = colors.HexColor("#BDBDBD")
        light_grey = colors.HexColor("#DADADA")
        scope_label = "CARGO" if self.loading_id else "SOURCING"

        # Outer frame
        pdf.setStrokeColor(light_grey)
        pdf.setLineWidth(0.9)
        pdf.rect(M, 16, CW, H - 32, fill=0, stroke=1)

        # Top right invoice heading with red cap bar
        pdf.setFillColor(orange)
        pdf.roundRect(M + CW - 252, H - 30, 236, 12, 3, fill=1, stroke=0)
        pdf.setFillColor(orange)
        pdf.setFont("Helvetica-Bold", 22)
        pdf.drawRightString(M + CW - 16, H - 54, f"{scope_label} PROFORMA")
        pdf.setFillColor(dark_grey)
        pdf.setFont("Helvetica", 8)
        pdf.drawRightString(
            M + CW - 16,
            H - 68,
            f"{scope_label.title()} | Invoice No: PI-{self.pk}",
        )

        # Logo row
        logo_path = Path(__file__).resolve().parent.parent.parent / "gmi_logo.png"
        if not logo_path.exists():
            logo_path = (
                Path(__file__).resolve().parent.parent
                / "static"
                / "images"
                / "gmi_logo.png"
            )
        logo_w, logo_h = 124, 44
        logo_x = M + 14
        logo_y = H - 68

        if logo_path.exists():
            pdf.setFillColor(colors.white)
            pdf.setStrokeColor(light_grey)
            pdf.roundRect(
                logo_x - 4, logo_y - 3, logo_w + 8, logo_h + 6, 4, fill=1, stroke=1
            )
            pdf.drawImage(
                str(logo_path),
                logo_x,
                logo_y,
                width=logo_w,
                height=logo_h,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )

        info_top = H - 114
        pdf.setFont("Helvetica-Bold", 7)
        pdf.setFillColor(dark_grey)
        pdf.drawString(M + 14, info_top + 18, "Bill To")
        pdf.setFillColor(black)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(M + 14, info_top + 4, self.transaction.customer.name[:38])
        pdf.setFont("Helvetica", 8)
        pdf.setFillColor(dark_grey)
        pdf.drawString(M + 14, info_top - 10, f"Ref: {self.transaction.transaction_id}")
        if self.supplier_name:
            pdf.drawString(
                M + 14, info_top - 22, f"Supplier: {self.supplier_name[:40]}"
            )

        date_str = self.created_at.strftime("%d/%m/%Y") if self.created_at else "—"
        valid_str = (
            self.validity_date.strftime("%d/%m/%Y") if self.validity_date else "—"
        )
        right_x = M + CW - 220
        pdf.setFont("Helvetica-Bold", 7)
        pdf.setFillColor(dark_grey)
        pdf.drawString(right_x, info_top + 18, "Total Due:")
        pdf.setFont("Helvetica-Bold", 10)
        pdf.setFillColor(black)
        pdf.drawRightString(M + CW, info_top + 18, f"USD $ {_fmt(self.total_amount)}")
        pdf.setFont("Helvetica", 8)
        pdf.setFillColor(dark_grey)
        pdf.drawString(right_x, info_top + 4, f"Date: {date_str}")
        pdf.drawString(right_x, info_top - 8, f"Due Date: {valid_str}")

        # Table geometry
        table_top = H - 228
        row_h = 20
        items = self.items if isinstance(self.items, list) else []
        row_count = max(len(items), 8)
        table_h = row_h * (row_count + 1)

        # Columns: SL | Description | Price | Qty | Amount
        x_sl = M + 26
        x_desc = M + 290
        x_price = M + 368
        x_qty = M + 430
        x_amt = M + CW

        # Header row: red (NO, ITEM DESCRIPTION), dark (PRICE, QTY, TOTAL)
        pdf.setFillColor(orange)
        pdf.rect(M, table_top, x_desc - M, row_h, fill=1, stroke=0)
        pdf.setFillColor(navy)
        pdf.rect(x_desc, table_top, (M + CW) - x_desc, row_h, fill=1, stroke=0)
        pdf.setStrokeColor(mid_grey)
        pdf.setLineWidth(0.7)
        pdf.rect(M, table_top - table_h + row_h, CW, table_h, fill=0, stroke=1)
        for x in (x_sl, x_desc, x_price, x_qty):
            pdf.line(x, table_top - table_h + row_h, x, table_top + row_h)

        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 7)
        hy = table_top + 7
        pdf.drawCentredString((M + x_sl) / 2, hy, "NO")
        pdf.drawString(x_sl + 6, hy, "ITEM DESCRIPTION")
        pdf.drawCentredString((x_desc + x_price) / 2, hy, "PRICE")
        pdf.drawCentredString((x_price + x_qty) / 2, hy, "QTY")
        pdf.drawCentredString((x_qty + x_amt) / 2, hy, "TOTAL")

        # Body rows
        body_top = table_top
        for i in range(row_count):
            y1 = body_top - ((i + 1) * row_h)
            pdf.setStrokeColor(mid_grey)
            pdf.setLineWidth(0.6)
            pdf.line(M, y1, M + CW, y1)

            if i < len(items):
                item = items[i]
                desc = str(item.get("description") or item.get("name") or "Item")
                qty = str(item.get("quantity") or "1")
                price = _fmt(item.get("sales_price") or item.get("unit_price"))
                amount = _fmt(
                    item.get("total") or item.get("amount") or item.get("unit_price")
                )
            else:
                desc = ""
                qty = ""
                price = ""
                amount = ""

            ty = y1 + 7
            pdf.setFont("Helvetica", 8)
            pdf.setFillColor(dark_grey)
            pdf.drawCentredString(
                (M + x_sl) / 2, ty, str(i + 1) if i < len(items) else ""
            )
            pdf.drawString(x_sl + 6, ty, desc[:54])
            pdf.drawRightString(x_price - 8, ty, f"${price}" if price else "")
            pdf.drawCentredString((x_price + x_qty) / 2, ty, qty)
            pdf.drawRightString(x_amt - 8, ty, f"${amount}" if amount else "")

        # Summary block (right)
        summary_y = table_top - table_h - 12
        summary_x = M + CW - 210

        pdf.setFont("Helvetica", 8)
        pdf.setFillColor(black)
        pdf.drawString(summary_x, summary_y, "Sub Total")
        pdf.drawRightString(M + CW, summary_y, f"${_fmt(self.subtotal)}")

        pdf.drawString(summary_x, summary_y - 14, "Sourcing Fee")
        pdf.drawRightString(M + CW, summary_y - 14, f"${_fmt(self.sourcing_fee)}")
        pdf.drawString(summary_x, summary_y - 28, "Handling Fee")
        pdf.drawRightString(M + CW, summary_y - 28, f"${_fmt(self.handling_fee)}")
        pdf.drawString(summary_x, summary_y - 42, "Shipping Fee")
        pdf.drawRightString(M + CW, summary_y - 42, f"${_fmt(self.shipping_fee)}")
        pdf.drawString(summary_x, summary_y - 56, "Vat tax 0%")
        pdf.drawRightString(M + CW, summary_y - 56, "$0.00")

        grand_y = summary_y - 74
        label_w = 72
        pdf.setFillColor(orange)
        pdf.rect(summary_x, grand_y, label_w, 12, fill=1, stroke=0)
        pdf.setFillColor(navy)
        pdf.rect(
            summary_x + label_w,
            grand_y,
            (M + CW) - (summary_x + label_w),
            12,
            fill=1,
            stroke=0,
        )
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(summary_x + (label_w / 2), grand_y + 3, "GRAND TOTAL")
        pdf.drawRightString(M + CW - 6, grand_y + 3, f"${_fmt(self.total_amount)}")

        # Signature (sits right after summary)
        sig_y = grand_y - 30
        pdf.setStrokeColor(colors.HexColor("#8A8A8A"))
        pdf.setLineWidth(0.6)
        pdf.line(summary_x + 70, sig_y + 4, summary_x + 162, sig_y + 4)
        pdf.setFont("Helvetica-Oblique", 7)
        pdf.setFillColor(colors.HexColor("#7B7B7B"))
        pdf.drawString(summary_x + 102, sig_y + 8, "Signature")
        pdf.setFont("Helvetica", 7)
        pdf.drawString(summary_x + 94, sig_y - 8, "Your Name Here")

        # Payment + terms block — pinned just above footer
        pay_y = 100
        pdf.setStrokeColor(colors.HexColor("#E6E8EA"))
        pdf.setLineWidth(0.6)
        pdf.line(M, pay_y + 52, M + CW, pay_y + 52)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.setFillColor(black)
        pdf.drawString(M, pay_y + 42, "Payment info")
        pdf.setFont("Helvetica", 7)
        pdf.setFillColor(dark_grey)
        pdf.drawString(
            M,
            pay_y + 30,
            "China Office: Guangzhou Baiyun District, ShaFeng 3rd Road, Jinsha B Station 2F | +86 177 0195 4464",
        )
        pdf.setFont("Helvetica-Bold", 8)
        pdf.setFillColor(black)
        pdf.drawString(
            M, pay_y + 16, "Uganda Office: Muyenga, Kampala | +256 768 049 940"
        )
        pdf.setFont("Helvetica", 7)
        pdf.setFillColor(dark_grey)
        pdf.drawString(
            M,
            pay_y + 5,
            "gmiterralinkinfo@gmail.com | www.gmi-terralink.com | Procurement | Freight | Mining | Translation | Money Transfer",
        )

        # Bottom contact row
        strip_y = 24
        pdf.setStrokeColor(light_grey)
        pdf.setLineWidth(0.7)
        pdf.line(M, strip_y + 24, M + CW, strip_y + 24)
        pdf.setFillColor(dark_grey)
        pdf.setFont("Helvetica", 7)
        pdf.drawString(M + 8, strip_y + 10, "+86 177 0195 4464")
        pdf.drawCentredString(M + (CW / 2), strip_y + 10, "gmiterralinkinfo@gmail.com")
        pdf.drawRightString(M + CW - 8, strip_y + 10, "+256 768 049 940")

        pdf.setFillColor(colors.HexColor("#C9A227"))
        pdf.roundRect(M + (CW / 2) - 110, strip_y - 3, 220, 8, 4, fill=1, stroke=0)

        # Reference
        pdf.setFillColor(colors.HexColor("#DEE3EA"))
        pdf.setFont("Helvetica", 6.5)
        pdf.drawRightString(
            M + CW - 6,
            strip_y + 28,
            f"PI-{self.pk} | {self.transaction.transaction_id}",
        )

        pdf.showPage()
        pdf.save()
        return buffer.getvalue()


class PurchaseOrder(models.Model):
    """Purchase Order generated when a client confirms and pays — authorises procurement."""

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("SENT", "Sent to Supplier"),
        ("FULFILLED", "Fulfilled"),
    )

    po_number = models.CharField(max_length=30, unique=True, editable=False)
    transaction = models.ForeignKey(
        Transaction, on_delete=models.PROTECT, related_name="purchase_orders"
    )
    proforma = models.ForeignKey(
        ProformaInvoice,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_orders",
    )
    final_invoice = models.ForeignKey(
        "FinalInvoice",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_orders",
    )
    parent_po = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="split_purchase_orders",
    )
    supplier_name = models.CharField(max_length=255)
    supplier_address = models.TextField(blank=True)
    items = models.JSONField(default=list)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="PENDING")
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="created_purchase_orders"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.po_number

    @classmethod
    def generate_po_number(cls):
        from django.utils import timezone

        now = timezone.now()
        prefix = f"PO-{now.year}{now.month:02d}-"
        latest = (
            cls.objects.filter(po_number__startswith=prefix)
            .order_by("-po_number")
            .first()
        )
        next_counter = 1
        if latest:
            try:
                next_counter = int(latest.po_number.split("-")[-1]) + 1
            except (ValueError, IndexError):
                next_counter = (
                    cls.objects.filter(po_number__startswith=prefix).count() + 1
                )
        return f"{prefix}{next_counter:04d}"

    def save(self, *args, **kwargs):
        if not self.po_number:
            self.po_number = self.generate_po_number()
        super().save(*args, **kwargs)

    @property
    def root_po(self):
        return self.parent_po or self

    @property
    def is_split(self):
        return self.parent_po_id is not None


class FinalInvoice(models.Model):
    """Binding invoice generated for confirmed transactions."""

    SHIPPING_MODE_CHOICES = (
        ("SEA", "Sea"),
        ("AIR", "Air"),
        ("CUSTOM", "Custom"),
    )

    transaction = models.ForeignKey(
        Transaction, on_delete=models.PROTECT, related_name="final_invoices"
    )
    loading = models.ForeignKey(
        "Loading",
        on_delete=models.PROTECT,
        related_name="final_invoices",
        null=True,
        blank=True,
    )
    items = models.JSONField(default=list)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    sourcing_fee = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    shipping_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    service_fee = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    shipping_mode = models.CharField(
        max_length=10, choices=SHIPPING_MODE_CHOICES, default="SEA"
    )
    route = models.CharField(max_length=100, default="China-Mombasa-Kampala")
    is_confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="created_final_invoices"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"FI-{self.pk or 'DRAFT'}-{self.transaction.transaction_id}"

    def save(self, *args, **kwargs):
        self.total_amount = (
            (self.subtotal or 0)
            + (self.sourcing_fee or 0)
            + (self.shipping_cost or 0)
            + (self.service_fee or 0)
        )
        if self.pk:
            original = FinalInvoice.objects.filter(pk=self.pk).first()
            if original and original.is_confirmed:
                tracked_fields = (
                    "items",
                    "subtotal",
                    "sourcing_fee",
                    "shipping_cost",
                    "service_fee",
                    "currency",
                    "shipping_mode",
                    "route",
                    "transaction_id",
                )
                for field in tracked_fields:
                    if getattr(original, field) != getattr(self, field):
                        raise ValidationError(
                            "Confirmed final invoice cannot be edited."
                        )
            if (
                original
                and not original.is_confirmed
                and self.is_confirmed
                and not self.confirmed_at
            ):
                self.confirmed_at = timezone.now()
        super().save(*args, **kwargs)

    def generate_pdf(self):
        from io import BytesIO
        from decimal import Decimal, InvalidOperation
        from pathlib import Path
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.utils import simpleSplit
        from reportlab.pdfgen import canvas

        def _fmt(value):
            try:
                return f"{Decimal(str(value or 0)):,.2f}"
            except (InvalidOperation, TypeError, ValueError):
                return "-"

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        W, H = A4
        M = 40
        CW = W - 2 * M

        # Colours
        band_bg = colors.HexColor("#1A1A1A")
        gold = colors.HexColor("#F4C21F")
        black = colors.HexColor("#111111")
        grey = colors.HexColor("#6C757D")
        tbl_border = colors.HexColor("#999999")
        page_border = colors.HexColor("#CCCCCC")
        scope_label = "CARGO" if self.loading_id else "SOURCING"

        # Outer page border to match the web preview carded sheet
        pdf.setStrokeColor(page_border)
        pdf.setLineWidth(0.8)
        pdf.rect(M, 36, CW, H - 72, fill=0, stroke=1)

        # ── 1. HEADER BAND ────────────────────────────────────────────────
        band_y = H - 36
        pdf.setFillColor(band_bg)
        pdf.rect(M, band_y, CW, 28, fill=1, stroke=0)
        pdf.setFillColor(gold)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(M + 10, band_y + 8, f"GMI TERRALINK {scope_label}")
        pdf.drawRightString(M + CW - 10, band_y + 8, f"{scope_label} INVOICE")

        # ── 2. CONTACTS LEFT, LOGO RIGHT ─────────────────────────────────
        logo_path = Path(__file__).resolve().parent.parent.parent / "gmi_logo.png"
        if not logo_path.exists():
            logo_path = (
                Path(__file__).resolve().parent.parent
                / "static"
                / "images"
                / "gmi_logo.png"
            )
        logo_w, logo_h = 120, 55
        logo_x = M + CW - logo_w
        logo_y = band_y - logo_h - 8

        if logo_path.exists():
            pdf.setFillColor(colors.white)
            pdf.setStrokeColor(page_border)
            pdf.roundRect(
                logo_x - 4, logo_y - 3, logo_w + 8, logo_h + 6, 4, fill=1, stroke=1
            )
            pdf.drawImage(
                str(logo_path),
                logo_x,
                logo_y,
                width=logo_w,
                height=logo_h,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )

        cy = band_y - 16
        pdf.setFillColor(black)
        pdf.setFont("Helvetica", 8.5)
        for line in [
            "CHINA OFFICE: Guangzhou Baiyun District, ShaFeng 3rd Road, Jinsha B Station 2F",
            "B239B (ECAT): +86 177 0195 4464",
            "UGANDA OFFICE: Muyenga, Kampala | +256 768 049 940",
            "gmiterralinkinfo@gmail.com | www.gmi-terralink.com",
        ]:
            pdf.drawString(M, cy, line)
            cy -= 13

        # ── 3. CARD BLOCKS: Bill To (left) + Invoice Details (right) ─────
        card_border = colors.HexColor("#DDDDDD")
        card_bg = colors.HexColor("#FAFAFA")
        card_title_color = colors.HexColor("#888888")
        card_gap = 20
        card_w = (CW - card_gap) / 2
        card_h = 86
        card_top = logo_y - 10
        lx = M
        rx_card = M + card_w + card_gap

        # Draw card backgrounds
        for cx in (lx, rx_card):
            pdf.setFillColor(card_bg)
            pdf.setStrokeColor(card_border)
            pdf.setLineWidth(0.6)
            pdf.roundRect(cx, card_top - card_h, card_w, card_h, 4, fill=1, stroke=1)

        # Left card — BILL TO
        pdf.setFont("Helvetica-Bold", 7)
        pdf.setFillColor(card_title_color)
        pdf.drawString(lx + 10, card_top - 14, "BILL TO")
        pdf.setStrokeColor(colors.HexColor("#EEEEEE"))
        pdf.line(lx + 10, card_top - 18, lx + card_w - 10, card_top - 18)

        pdf.setFont("Helvetica-Bold", 9)
        pdf.setFillColor(black)
        pdf.drawString(lx + 10, card_top - 32, self.transaction.customer.name)
        pdf.setFont("Helvetica", 8.5)
        pdf.drawString(
            lx + 10, card_top - 46, f"Ref: {self.transaction.transaction_id}"
        )
        pdf.drawString(lx + 10, card_top - 60, f"Route: {self.route}")

        # Right card — INVOICE DETAILS
        pdf.setFont("Helvetica-Bold", 7)
        pdf.setFillColor(card_title_color)
        pdf.drawString(rx_card + 10, card_top - 14, "INVOICE DETAILS")
        pdf.setStrokeColor(colors.HexColor("#EEEEEE"))
        pdf.line(rx_card + 10, card_top - 18, rx_card + card_w - 10, card_top - 18)

        date_str = self.created_at.strftime("%d/%m/%Y") if self.created_at else "—"
        status_str = "Confirmed" if self.is_confirmed else "Pending"
        rdata = [
            ("Invoice #", f"FI-{self.pk}"),
            ("Invoice Date", date_str),
            ("Shipping", self.get_shipping_mode_display()),
        ]
        rr_y = card_top - 32
        for lbl, val in rdata:
            pdf.setFont("Helvetica", 8.5)
            pdf.setFillColor(grey)
            pdf.drawString(rx_card + 10, rr_y, lbl)
            pdf.setFont("Helvetica-Bold", 8.5)
            pdf.setFillColor(black)
            pdf.drawString(rx_card + 80, rr_y, str(val))
            rr_y -= 14

        pdf.setFont("Helvetica", 8.5)
        pdf.setFillColor(grey)
        pdf.drawString(rx_card + 10, rr_y, "Status")
        badge_fill = colors.HexColor("#198754") if self.is_confirmed else gold
        badge_text_color = colors.white if self.is_confirmed else black
        badge_w = max(42, len(status_str) * 4.5 + 10)
        pdf.setFillColor(badge_fill)
        pdf.setStrokeColor(badge_fill)
        pdf.roundRect(rx_card + 80, rr_y - 2, badge_w, 12, 3, fill=1, stroke=0)
        pdf.setFont("Helvetica-Bold", 7.5)
        pdf.setFillColor(badge_text_color)
        pdf.drawCentredString(rx_card + 80 + (badge_w / 2), rr_y + 1, status_str)

        # ── 4. LINE ITEMS TABLE ───────────────────────────────────────────
        tbl_top = card_top - card_h - 40

        # Column positions
        col_qty_r = M + 50
        col_desc_r = M + CW - 220
        col_price_r = M + CW - 110
        col_total_r = M + CW

        # Header row (gold background)
        th_h = 20
        th_y = tbl_top
        pdf.setFillColor(gold)
        pdf.rect(M, th_y, CW, th_h, fill=1, stroke=0)
        pdf.setStrokeColor(tbl_border)
        pdf.setLineWidth(0.7)
        pdf.rect(M, th_y, CW, th_h, fill=0, stroke=1)
        for x in (col_qty_r, col_desc_r, col_price_r):
            pdf.line(x, th_y, x, th_y + th_h)

        pdf.setFillColor(black)
        pdf.setFont("Helvetica-Bold", 8.5)
        ty = th_y + 6
        pdf.drawCentredString((M + col_qty_r) / 2, ty, "QTY")
        pdf.drawString(col_qty_r + 6, ty, "DESCRIPTION")
        pdf.drawCentredString((col_desc_r + col_price_r) / 2, ty, "UNIT PRICE")
        pdf.drawCentredString((col_price_r + col_total_r) / 2, ty, "AMOUNT")

        # Body rows
        min_row_h = 20
        line_gap = 10
        row_top = th_y
        items = self.items if isinstance(self.items, list) else []
        min_body_rows = max(len(items), 1)
        desc_w = col_desc_r - col_qty_r - 12

        for i in range(min_body_rows):
            desc_lines = [""]
            qty = ""
            price = ""
            total = ""
            pdf.setStrokeColor(tbl_border)
            pdf.setLineWidth(0.7)

            if i < len(items):
                item = items[i]
                desc = str(item.get("description") or item.get("name") or "Service")
                desc_lines = simpleSplit(desc, "Helvetica", 8.5, desc_w) or [desc]
                qty = str(item.get("quantity") or "1")
                price = _fmt(item.get("sales_price") or item.get("unit_price"))
                total = _fmt(item.get("total") or item.get("amount"))

            row_h = max(min_row_h, 12 + (len(desc_lines) * line_gap))
            row_bottom = row_top - row_h
            numeric_text_y = row_bottom + ((row_h - 8.5) / 2)

            # Vertical lines only (no horizontal between rows)
            for x in (M, col_qty_r, col_desc_r, col_price_r, M + CW):
                pdf.line(x, row_bottom, x, row_top)

            text_y = row_top - 13
            pdf.setFont("Helvetica", 8.5)
            pdf.setFillColor(black)
            if qty:
                pdf.drawCentredString((M + col_qty_r) / 2, numeric_text_y, qty)
            for offset, line in enumerate(desc_lines):
                pdf.drawString(col_qty_r + 6, text_y - (offset * line_gap), line)
            if price:
                pdf.drawCentredString(
                    (col_desc_r + col_price_r) / 2, numeric_text_y, price
                )
            if total:
                pdf.setFont("Helvetica-Bold", 8.5)
                pdf.drawCentredString(
                    (col_price_r + col_total_r) / 2, numeric_text_y, total
                )

            row_top = row_bottom

        # Bottom border of body area
        pdf.setStrokeColor(tbl_border)
        pdf.setLineWidth(0.7)
        pdf.line(M, row_top, M + CW, row_top)

        # Summary rows for fees and total
        summary_rows = [
            ("Items Subtotal", self.subtotal, colors.HexColor("#FAFAFA")),
            ("Sourcing Fee", self.sourcing_fee, colors.HexColor("#FAFAFA")),
            ("Handling Fee", self.service_fee, colors.HexColor("#FAFAFA")),
            ("Shipping Fee", self.shipping_cost, colors.HexColor("#FAFAFA")),
        ]
        summary_y = row_top - min_row_h
        for label, value, bg in summary_rows:
            pdf.setFillColor(bg)
            pdf.rect(
                col_desc_r,
                summary_y,
                col_price_r - col_desc_r,
                min_row_h,
                fill=1,
                stroke=0,
            )
            pdf.rect(
                col_price_r,
                summary_y,
                col_total_r - col_price_r,
                min_row_h,
                fill=1,
                stroke=0,
            )
            pdf.setStrokeColor(tbl_border)
            pdf.setLineWidth(0.9)
            pdf.rect(
                col_desc_r,
                summary_y,
                col_price_r - col_desc_r,
                min_row_h,
                fill=0,
                stroke=1,
            )
            pdf.rect(
                col_price_r,
                summary_y,
                col_total_r - col_price_r,
                min_row_h,
                fill=0,
                stroke=1,
            )
            pdf.setFont("Helvetica-Bold", 9.5)
            pdf.setFillColor(black)
            pdf.drawCentredString(
                (col_desc_r + col_price_r) / 2, summary_y + 6, label.upper()
            )
            pdf.setFont("Helvetica-Bold", 10.5)
            pdf.drawCentredString(
                (col_price_r + col_total_r) / 2,
                summary_y + 5,
                f"${_fmt(value)}",
            )
            summary_y -= min_row_h

        total_y = summary_y
        total_bg = colors.HexColor("#FFF1B8")
        total_amt_bg = gold
        pdf.setFillColor(total_bg)
        pdf.rect(
            col_desc_r, total_y, col_price_r - col_desc_r, min_row_h, fill=1, stroke=0
        )
        pdf.setFillColor(total_amt_bg)
        pdf.rect(
            col_price_r, total_y, col_total_r - col_price_r, min_row_h, fill=1, stroke=0
        )
        pdf.setStrokeColor(tbl_border)
        pdf.setLineWidth(1.1)
        pdf.rect(
            col_desc_r, total_y, col_price_r - col_desc_r, min_row_h, fill=0, stroke=1
        )
        pdf.rect(
            col_price_r, total_y, col_total_r - col_price_r, min_row_h, fill=0, stroke=1
        )
        pdf.setFont("Helvetica-Bold", 10.5)
        pdf.setFillColor(black)
        pdf.drawCentredString((col_desc_r + col_price_r) / 2, total_y + 6, "TOTAL")
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawCentredString(
            (col_price_r + col_total_r) / 2, total_y + 5, f"${_fmt(self.total_amount)}"
        )

        # Ref tag
        pdf.setFont("Helvetica", 7)
        pdf.setFillColor(grey)
        pdf.drawRightString(
            M + CW, 40, f"FI-{self.pk}  |  {self.transaction.transaction_id}"
        )

        pdf.showPage()
        pdf.save()
        return buffer.getvalue()


class TransactionPaymentRecord(models.Model):
    """Payment instalment recorded against a sourcing Transaction's FinalInvoice."""

    PAYMENT_METHOD_CHOICES = (
        ("cash", "Cash"),
        ("bank_transfer", "Bank Transfer"),
        ("cheque", "Cheque"),
        ("mobile_money", "Mobile Money"),
        ("other", "Other"),
    )

    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.PROTECT,
        related_name="payment_records",
    )
    final_invoice = models.ForeignKey(
        FinalInvoice,
        on_delete=models.PROTECT,
        related_name="payment_records",
        null=True,
        blank=True,
        help_text="Invoice this payment is applied to.",
    )
    amount_due_snapshot = models.DecimalField(
        max_digits=14, decimal_places=2, default=0
    )
    is_full_payment = models.BooleanField(default=False)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    cash_received = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    change_given = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance_after = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payment_date = models.DateTimeField(default=timezone.now)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="sourcing_payment_records"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-payment_date"]

    def __str__(self):
        return f"Payment {self.amount} {self.currency} for {self.transaction.transaction_id}"

    def save(self, *args, **kwargs):
        if self.cash_received is None:
            self.change_given = Decimal("0")
        elif self.cash_received >= self.amount:
            self.change_given = self.cash_received - self.amount
        else:
            self.change_given = Decimal("0")
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            try:
                client_name = self.transaction.customer.name
            except Exception:
                client_name = "Unknown"
            Receipt.objects.get_or_create(
                sourcing_payment=self,
                defaults={
                    "amount": self.amount,
                    "currency": self.currency,
                    "issued_to": client_name,
                },
            )


class Receipt(models.Model):
    """Immutable receipt auto-generated when any payment is recorded."""

    # Source: either a logistics PaymentTransaction or a sourcing TransactionPaymentRecord
    logistics_payment = models.OneToOneField(
        PaymentTransaction,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="receipt",
    )
    sourcing_payment = models.OneToOneField(
        TransactionPaymentRecord,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="receipt",
    )
    receipt_number = models.CharField(max_length=25, unique=True, editable=False)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    issued_to = models.CharField(max_length=255)  # snapshot of client name at issuance
    issued_at = models.DateTimeField(auto_now_add=True)
    is_reversed = models.BooleanField(default=False)
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reversed_receipts",
    )
    reversal_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-issued_at"]
        permissions = (("can_reverse_receipts", "Can reverse or refund receipts"),)

    def __str__(self):
        return self.receipt_number

    @classmethod
    def generate_receipt_number(cls):
        now = timezone.now()
        prefix = f"RCT-{now.year}{now.month:02d}-"
        latest = (
            cls.objects.filter(receipt_number__startswith=prefix)
            .order_by("-receipt_number")
            .first()
        )
        next_counter = 1
        if latest:
            try:
                next_counter = int(latest.receipt_number.split("-")[-1]) + 1
            except (ValueError, IndexError):
                next_counter = (
                    cls.objects.filter(receipt_number__startswith=prefix).count() + 1
                )
        return f"{prefix}{next_counter:04d}"

    def save(self, *args, **kwargs):
        if self.pk:
            # Immutable once created — only reversal fields may change
            original = Receipt.objects.filter(pk=self.pk).first()
            if original:
                locked_fields = (
                    "receipt_number",
                    "amount",
                    "currency",
                    "issued_to",
                    "logistics_payment_id",
                    "sourcing_payment_id",
                )
                for field in locked_fields:
                    if getattr(original, field) != getattr(self, field):
                        raise ValidationError(
                            "Receipt records are immutable and cannot be modified."
                        )
        if not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
        super().save(*args, **kwargs)

    def generate_pdf(self):
        from io import BytesIO
        from pathlib import Path
        from reportlab.lib import colors as rcolors
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase.pdfmetrics import stringWidth
        from reportlab.pdfgen import canvas as rcanvas

        buffer = BytesIO()
        pdf = rcanvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        margin = 40
        primary = rcolors.HexColor("#1E1A23")
        accent = rcolors.HexColor("#F4C21F")
        border = rcolors.HexColor("#D9D9D9")
        muted = rcolors.HexColor("#666666")
        soft_fill = rcolors.HexColor("#FFF2C2")
        danger = rcolors.HexColor("#9C2F2F")

        def draw_info_box(x, y, box_width, box_height, title, lines):
            pdf.setFillColor(rcolors.white)
            pdf.setStrokeColor(border)
            pdf.rect(x, y, box_width, box_height, fill=1, stroke=1)
            pdf.setFillColor(muted)
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(x + 12, y + box_height - 16, title.upper())
            pdf.setFillColor(rcolors.black)
            pdf.setFont("Helvetica", 9)
            line_y = y + box_height - 34
            for line in lines[:5]:
                pdf.drawString(x + 12, line_y, str(line)[:88])
                line_y -= 14

        def draw_wrapped_lines(
            x, y_top, text, max_width, font_name="Helvetica", font_size=8, line_gap=11
        ):
            words = str(text).split()
            if not words:
                return y_top
            current = words[0]
            lines = []
            for word in words[1:]:
                trial = f"{current} {word}"
                if stringWidth(trial, font_name, font_size) <= max_width:
                    current = trial
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
            pdf.setFont(font_name, font_size)
            for line in lines:
                pdf.drawString(x, y_top, line)
                y_top -= line_gap
            return y_top

        _draw_standard_doc_header(
            pdf,
            width,
            height,
            "OFFICIAL RECEIPT",
            self.receipt_number,
        )

        # Resolve client/contact details from whichever payment source created this receipt.
        client = None
        if self.logistics_payment and self.logistics_payment.payment:
            loading = self.logistics_payment.payment.loading
            client = getattr(loading, "client", None)
        elif self.sourcing_payment and self.sourcing_payment.transaction:
            client = getattr(self.sourcing_payment.transaction, "customer", None)

        payment_method = ""
        if self.logistics_payment:
            payment_method = self.logistics_payment.get_payment_method_display()
        elif self.sourcing_payment:
            payment_method = self.sourcing_payment.get_payment_method_display()

        payment_type = (
            "Logistics Shipment" if self.logistics_payment else "Sourcing / Trade"
        )

        top = height - 108
        content_width = width - (2 * margin)

        pdf.setFillColor(rcolors.black)
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(margin, top, self.receipt_number)
        pdf.setFont("Helvetica", 10)
        pdf.setFillColor(rcolors.HexColor("#555555"))
        pdf.drawString(margin, top - 16, f"Issued to {self.issued_to}")
        meta_y = top - 30
        meta_parts = [
            self.issued_at.strftime("%d %B %Y %H:%M"),
            payment_type,
            payment_method or "-",
        ]
        pdf.drawString(margin, meta_y, "   |   ".join(meta_parts))

        chip_w = 190
        chip_h = 34
        chip_x = width - margin - chip_w
        chip_y = top - 18
        pdf.setFillColor(soft_fill)
        pdf.setStrokeColor(soft_fill)
        pdf.roundRect(chip_x, chip_y, chip_w, chip_h, 14, fill=1, stroke=0)
        pdf.setFillColor(primary)
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawCentredString(
            chip_x + (chip_w / 2), chip_y + 11, f"{self.currency} {self.amount:,.2f}"
        )

        content_top = top - 54
        if self.is_reversed:
            alert_y = content_top - 8
            pdf.setFillColor(rcolors.HexColor("#F8DEDE"))
            pdf.setStrokeColor(rcolors.HexColor("#E5B9B9"))
            pdf.roundRect(margin, alert_y, content_width, 28, 12, fill=1, stroke=1)
            pdf.setFillColor(danger)
            pdf.setFont("Helvetica-Bold", 10)
            text = f"Reversed on {self.reversed_at.strftime('%d %b %Y %H:%M')}"
            if self.reversed_by:
                text += f" by {self.reversed_by.username}"
            if self.reversal_notes:
                text += f" - {self.reversal_notes}"
            pdf.drawString(margin + 12, alert_y + 10, text)
            content_top = alert_y - 18

        if client:
            client_lines = [f"Name: {client.name}"]
            client_lines.append(
                f"Contact: {client.contact_person}{' | ' + client.phone if client.phone else ''}"
            )
            if client.email:
                client_lines.append(f"Email: {client.email}")
            if client.address:
                client_lines.append(f"Address: {client.address}")
        else:
            client_lines = ["Client details not available."]

        left_y = content_top - 96
        left_h = 96
        right_h = 96
        gutter = 14
        left_w = int(content_width * 0.58)
        right_w = content_width - left_w - gutter
        right_x = margin + left_w + gutter

        summary_lines = [
            payment_type,
            payment_method or "-",
        ]
        if self.logistics_payment and self.logistics_payment.payment:
            summary_lines.append(
                f"Loading Ref: {self.logistics_payment.payment.loading.loading_id}"
            )
        elif self.sourcing_payment and self.sourcing_payment.transaction:
            summary_lines.append(
                f"Transaction: {self.sourcing_payment.transaction.transaction_id}"
            )
            summary_lines.append(
                "Payment Type: "
                + (
                    "Full Payment"
                    if self.sourcing_payment.is_full_payment
                    else "Partial Payment"
                )
            )

        draw_info_box(margin, left_y, left_w, left_h, "Client Details", client_lines)

        pdf.setFillColor(rcolors.white)
        pdf.setStrokeColor(border)
        pdf.rect(right_x, left_y, right_w, right_h, fill=1, stroke=1)
        pdf.setFillColor(muted)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(right_x + 12, left_y + right_h - 16, "AMOUNT RECEIVED")
        pdf.setFillColor(primary)
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(
            right_x + 12, left_y + right_h - 42, f"{self.currency} {self.amount:,.2f}"
        )
        pdf.setFont("Helvetica", 8.5)
        fact_y = left_y + right_h - 60
        pdf.setStrokeColor(border)
        for line in summary_lines[:4]:
            pdf.line(right_x + 12, fact_y, right_x + right_w - 12, fact_y)
            fact_y -= 12
            pdf.setFillColor(muted)
            if ": " in line:
                key, value = line.split(": ", 1)
            else:
                key, value = ("Type", line)
            pdf.drawString(right_x + 12, fact_y + 3, key)
            pdf.setFillColor(primary)
            pdf.drawRightString(right_x + right_w - 12, fact_y + 3, value[:26])
            fact_y -= 8

        detail_y = left_y - 78
        if self.sourcing_payment:
            pdf.setFillColor(rcolors.white)
            pdf.setStrokeColor(border)
            pdf.rect(margin, detail_y, content_width, 64, fill=1, stroke=1)
            pdf.setFillColor(muted)
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(margin + 12, detail_y + 48, "TRADE PAYMENT DETAILS")
            pdf.setFillColor(rcolors.black)
            pdf.setFont("Helvetica", 9)
            pdf.drawString(
                margin + 12,
                detail_y + 32,
                f"Amount Due At Receipt: {self.sourcing_payment.amount_due_snapshot:,.2f} {self.sourcing_payment.currency}",
            )
            pdf.drawString(
                margin + 12,
                detail_y + 18,
                f"Balance After Payment: {self.sourcing_payment.balance_after:,.2f} {self.sourcing_payment.currency}",
            )
            if self.sourcing_payment.final_invoice_id:
                pdf.drawString(
                    margin + 300,
                    detail_y + 32,
                    f"Linked Invoice: FI-{self.sourcing_payment.final_invoice_id}",
                )
            if self.sourcing_payment.cash_received:
                pdf.drawString(
                    margin + 300,
                    detail_y + 18,
                    f"Cash Received: {self.sourcing_payment.cash_received:,.2f} {self.sourcing_payment.currency}",
                )
                pdf.drawString(
                    margin + 300,
                    detail_y + 4,
                    f"Change Returned: {self.sourcing_payment.change_given:,.2f} {self.sourcing_payment.currency}",
                )

        footer_top = detail_y - 20 if self.sourcing_payment else left_y - 20
        pdf.setStrokeColor(border)
        pdf.line(margin, footer_top, width - margin, footer_top)
        pdf.setFillColor(rcolors.HexColor("#6C757D"))
        footer_y = footer_top - 12
        footer_width = content_width
        footer_lines = [
            "International Terms & Conditions: Prices are quoted Ex-Works unless otherwise agreed in writing. Bank charges, customs duties, taxes, demurrage, and destination fees are for the buyer account unless expressly included.",
            "Delivery timelines are estimates and may vary due to carrier schedules, port operations, customs controls, force majeure, or regulatory actions. Claims for shortages or damage must be submitted in writing within 3 business days of delivery.",
            "Disputes are resolved amicably first, failing which arbitration applies under mutually agreed commercial rules. Email confirmations and signed copies form part of the binding commercial record.",
        ]
        for paragraph in footer_lines:
            footer_y = draw_wrapped_lines(
                margin,
                footer_y,
                paragraph,
                footer_width,
                font_name="Helvetica",
                font_size=7,
                line_gap=9,
            )
            footer_y -= 3
        pdf.setFont("Helvetica", 7)
        pdf.drawString(
            margin,
            footer_y - 2,
            "gmiterralinkinfo@gmail.com | +256 768 049 940 | +86 177 0195 4464 | www.gmi-terralink.com",
        )

        pdf.showPage()
        pdf.save()
        return buffer.getvalue()


class ShipmentWorkflow(models.Model):
    """Operational shipment aggregate supporting FCL and LCL flows."""

    MODE_CHOICES = (
        ("FCL", "Full Container Load"),
        ("LCL", "Groupage (LCL)"),
    )
    STATUS_CHOICES = (
        ("RECEIVED", "Received"),
        ("VERIFIED", "Verified"),
        ("ALLOCATED", "Allocated"),
        ("LOADED", "Loaded"),
        ("IN_TRANSIT", "In Transit"),
        ("ARRIVED", "Arrived"),
        ("DELIVERED", "Delivered"),
        ("CANCELLED", "Cancelled"),
    )

    shipment_number = models.CharField(max_length=32, unique=True, editable=False)
    mode = models.CharField(max_length=3, choices=MODE_CHOICES)
    client = models.ForeignKey(
        Client, on_delete=models.PROTECT, related_name="workflow_shipments"
    )
    loading = models.OneToOneField(
        Loading,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_shipment",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="RECEIVED")
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    warehouse_location = models.CharField(max_length=255)
    lcl_rate_per_kg = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fcl_flat_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    handling_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    storage_fee_per_day = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="created_workflow_shipments"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.shipment_number

    @classmethod
    def generate_shipment_number(cls, mode):
        year_short = timezone.now().strftime("%y")
        prefix = f"SHP-{mode}-UG-{year_short}-"
        next_counter = 1
        existing = cls.objects.filter(shipment_number__startswith=prefix).values_list(
            "shipment_number", flat=True
        )
        for shipment_number in existing:
            try:
                counter = int(str(shipment_number).split("-")[-1])
                next_counter = max(next_counter, counter + 1)
            except (TypeError, ValueError):
                continue
        return f"{prefix}{next_counter:04d}"

    def save(self, *args, **kwargs):
        if not self.shipment_number:
            self.shipment_number = self.generate_shipment_number(self.mode)
        super().save(*args, **kwargs)


class CargoItemWorkflow(models.Model):
    """Child cargo lines under a shipment aggregate (supports partial delivery)."""

    STATUS_CHOICES = (
        ("RECEIVED", "Received"),
        ("VERIFIED", "Verified"),
        ("ALLOCATED", "Allocated"),
        ("LOADED", "Loaded"),
        ("IN_TRANSIT", "In Transit"),
        ("ARRIVED", "Arrived"),
        ("PARTIALLY_DELIVERED", "Partially Delivered"),
        ("DELIVERED", "Delivered"),
        ("CANCELLED", "Cancelled"),
    )

    INVENTORY_STATE_CHOICES = (
        ("WAREHOUSE", "Warehouse Stock"),
        ("RESERVED", "Reserved"),
        ("IN_TRANSIT", "In Transit"),
        ("DELIVERED", "Delivered"),
    )

    cargo_number = models.CharField(max_length=32, unique=True, editable=False)
    shipment = models.ForeignKey(
        ShipmentWorkflow, on_delete=models.CASCADE, related_name="cargo_items"
    )
    description = models.TextField()
    package_count = models.PositiveIntegerField(default=1)
    quantity_total = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    quantity_delivered = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    actual_weight_kg = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    volumetric_weight_kg = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )
    chargeable_weight_kg = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="RECEIVED")
    inventory_state = models.CharField(
        max_length=16, choices=INVENTORY_STATE_CHOICES, default="WAREHOUSE"
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name="created_workflow_cargo_items",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["shipment", "created_at"]
        constraints = [
            models.CheckConstraint(
                check=Q(quantity_total__gt=0),
                name="workflow_cargo_quantity_total_gt_zero",
            ),
            models.CheckConstraint(
                check=Q(quantity_delivered__gte=0),
                name="workflow_cargo_quantity_delivered_non_negative",
            ),
            models.CheckConstraint(
                check=Q(quantity_delivered__lte=F("quantity_total")),
                name="workflow_cargo_quantity_delivered_lte_total",
            ),
        ]

    def __str__(self):
        return f"{self.cargo_number} ({self.shipment.shipment_number})"

    @classmethod
    def generate_cargo_number(cls):
        year_short = timezone.now().strftime("%y")
        prefix = f"CGI-UG-{year_short}-"
        next_counter = 1
        existing = cls.objects.filter(cargo_number__startswith=prefix).values_list(
            "cargo_number", flat=True
        )
        for cargo_number in existing:
            try:
                counter = int(str(cargo_number).split("-")[-1])
                next_counter = max(next_counter, counter + 1)
            except (TypeError, ValueError):
                continue
        return f"{prefix}{next_counter:04d}"

    def save(self, *args, **kwargs):
        if not self.cargo_number:
            self.cargo_number = self.generate_cargo_number()
        self.chargeable_weight_kg = max(
            self.actual_weight_kg, self.volumetric_weight_kg
        )
        super().save(*args, **kwargs)


class InventoryPosition(models.Model):
    """Single source of truth for inventory balance by cargo item."""

    cargo_item = models.OneToOneField(
        CargoItemWorkflow,
        on_delete=models.CASCADE,
        related_name="inventory_position",
    )
    qty_warehouse = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    qty_reserved = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    qty_in_transit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    qty_delivered = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    version = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=Q(qty_warehouse__gte=0)
                & Q(qty_reserved__gte=0)
                & Q(qty_in_transit__gte=0)
                & Q(qty_delivered__gte=0),
                name="inventory_position_non_negative_balances",
            )
        ]

    def __str__(self):
        return f"Position {self.cargo_item.cargo_number}"


class DomainEvent(models.Model):
    """Operational outbox event (idempotent, durable, replayable)."""

    aggregate_type = models.CharField(max_length=40)
    aggregate_id = models.CharField(max_length=64)
    event_type = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=120, unique=True)
    payload = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="created_domain_events",
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type}::{self.aggregate_type}::{self.aggregate_id}"


class InventoryMovement(models.Model):
    """Append-only inventory movement log generated from workflow events."""

    MOVEMENT_CHOICES = (
        ("RECEIVED", "Received"),
        ("RESERVED", "Reserved"),
        ("RELEASED", "Released"),
        ("LOADED", "Loaded"),
        ("DELIVERED", "Delivered"),
        ("ADJUSTMENT", "Adjustment"),
    )

    position = models.ForeignKey(
        InventoryPosition,
        on_delete=models.CASCADE,
        related_name="movements",
    )
    cargo_item = models.ForeignKey(
        CargoItemWorkflow,
        on_delete=models.CASCADE,
        related_name="inventory_movements",
    )
    shipment = models.ForeignKey(
        ShipmentWorkflow,
        on_delete=models.CASCADE,
        related_name="inventory_movements",
    )
    movement_type = models.CharField(max_length=16, choices=MOVEMENT_CHOICES)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    from_state = models.CharField(max_length=20, blank=True)
    to_state = models.CharField(max_length=20, blank=True)
    idempotency_key = models.CharField(max_length=120, unique=True)
    event = models.ForeignKey(
        DomainEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_movements",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="created_inventory_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                check=Q(quantity__gt=0),
                name="inventory_movement_quantity_gt_zero",
            )
        ]

    def __str__(self):
        return f"{self.cargo_item.cargo_number} {self.movement_type} {self.quantity}"


class WorkflowTransitionLog(models.Model):
    """Immutable audit of status transitions for shipment and cargo entities."""

    ENTITY_CHOICES = (("SHIPMENT", "Shipment"), ("CARGO", "Cargo"))

    entity_type = models.CharField(max_length=16, choices=ENTITY_CHOICES)
    entity_id = models.PositiveBigIntegerField()
    from_status = models.CharField(max_length=30)
    to_status = models.CharField(max_length=30)
    notes = models.TextField(blank=True)
    event = models.ForeignKey(
        DomainEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transition_logs",
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="created_transition_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.entity_type}#{self.entity_id}: {self.from_status} -> {self.to_status}"


class BillingCharge(models.Model):
    """Operationally-derived billable line items."""

    CHARGE_TYPE_CHOICES = (
        ("LCL_FREIGHT", "LCL Freight"),
        ("HANDLING", "Handling"),
        ("STORAGE", "Storage"),
        ("FCL_FLAT", "FCL Flat"),
        ("PORT", "Port"),
        ("TRANSPORT", "Transport"),
        ("DEMURRAGE", "Demurrage"),
        ("ADJUSTMENT", "Adjustment"),
    )

    STATUS_CHOICES = (
        ("OPEN", "Open"),
        ("INVOICED", "Invoiced"),
        ("VOID", "Void"),
    )

    shipment = models.ForeignKey(
        ShipmentWorkflow,
        on_delete=models.CASCADE,
        related_name="billing_charges",
    )
    cargo_item = models.ForeignKey(
        CargoItemWorkflow,
        on_delete=models.CASCADE,
        related_name="billing_charges",
        null=True,
        blank=True,
    )
    charge_type = models.CharField(max_length=20, choices=CHARGE_TYPE_CHOICES)
    trigger_event = models.CharField(max_length=64)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="USD")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="OPEN")
    idempotency_key = models.CharField(max_length=120, unique=True)
    event = models.ForeignKey(
        DomainEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="billing_charges",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.shipment.shipment_number} {self.charge_type} {self.amount}"

    def save(self, *args, **kwargs):
        self.amount = (self.quantity or 0) * (self.unit_price or 0)
        super().save(*args, **kwargs)


class BillingInvoice(models.Model):
    """Accounts receivable invoice for shipment/cargo operations."""

    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("ISSUED", "Issued"),
        ("PARTIALLY_PAID", "Partially Paid"),
        ("PAID", "Paid"),
        ("VOID", "Void"),
    )

    invoice_number = models.CharField(max_length=32, unique=True, editable=False)
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="workflow_billing_invoices",
    )
    shipment = models.ForeignKey(
        ShipmentWorkflow,
        on_delete=models.CASCADE,
        related_name="billing_invoices",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    issued_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.invoice_number

    @classmethod
    def generate_invoice_number(cls):
        year_short = timezone.now().strftime("%y")
        prefix = f"INV-OPS-UG-{year_short}-"
        next_counter = 1
        existing = cls.objects.filter(invoice_number__startswith=prefix).values_list(
            "invoice_number", flat=True
        )
        for invoice_number in existing:
            try:
                counter = int(str(invoice_number).split("-")[-1])
                next_counter = max(next_counter, counter + 1)
            except (TypeError, ValueError):
                continue
        return f"{prefix}{next_counter:04d}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        self.balance = max((self.total_amount or 0) - (self.amount_paid or 0), 0)
        if self.balance == 0 and self.total_amount > 0:
            self.status = "PAID"
        elif self.amount_paid > 0 and self.balance > 0:
            self.status = "PARTIALLY_PAID"
        super().save(*args, **kwargs)


class BillingInvoiceLine(models.Model):
    """Invoice line linked back to source charge for full traceability."""

    invoice = models.ForeignKey(
        BillingInvoice, on_delete=models.CASCADE, related_name="lines"
    )
    charge = models.OneToOneField(
        BillingCharge,
        on_delete=models.PROTECT,
        related_name="invoice_line",
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.description}"


class BillingPayment(models.Model):
    """Partial/complete payment records for workflow invoices."""

    METHOD_CHOICES = (
        ("CASH", "Cash"),
        ("BANK_TRANSFER", "Bank Transfer"),
        ("MOBILE_MONEY", "Mobile Money"),
        ("CHEQUE", "Cheque"),
    )

    invoice = models.ForeignKey(
        BillingInvoice,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="CASH")
    reference = models.CharField(max_length=120, blank=True)
    idempotency_key = models.CharField(max_length=120, unique=True)
    paid_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="created_workflow_payments",
    )

    class Meta:
        ordering = ["-paid_at"]
        constraints = [
            models.CheckConstraint(
                check=Q(amount__gt=0),
                name="billing_payment_amount_gt_zero",
            )
        ]

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.amount}"


# NOTE: Commission and COMMISSION_CURRENCY_CHOICES were extracted to
# ``logistics.models.commission`` as the first proof of the package split.
# They are re-exported from ``logistics.models.__init__`` so existing imports
# continue to work unchanged.
class SupplierPayment(models.Model):
    """Money paid out to a supplier against a Purchase Order."""

    METHOD_CHOICES = (
        ("BANK", "Bank Transfer"),
        ("CASH", "Cash"),
        ("MOBILE", "Mobile Money"),
        ("CARD", "Card"),
        ("OTHER", "Other"),
    )

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.PROTECT,
        related_name="supplier_payments",
    )
    supplier_name = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default="BANK")
    reference = models.CharField(max_length=120, blank=True)
    paid_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_supplier_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-paid_at", "-id"]

    def __str__(self):
        return f"{self.purchase_order.po_number} - {self.amount} {self.currency}"
