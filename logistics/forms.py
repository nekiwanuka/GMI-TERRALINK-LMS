"""
Django forms for the logistics management system
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Sum
from decimal import Decimal, InvalidOperation
import ast
import json
import re

_ACRONYMS = {
    "bl": "BL",
    "cbm": "CBM",
    "fi": "FI",
    "gmi": "GMI",
    "gtl": "GTL",
    "kg": "KG",
    "lcl": "LCL",
    "ltd": "LTD",
    "pi": "PI",
    "po": "PO",
    "ug": "UG",
    "uk": "UK",
    "usa": "USA",
    "usd": "USD",
}

_PRESERVE_TEXT_FIELD_NAMES = {
    "password",
    "password1",
    "password2",
    "phone",
    "received_by_phone",
    "username",
    "notes",
    "remarks",
    "warehouse_notes",
    "closure_notes",
    "verification_notes",
    "reversal_notes",
    "items",
    "item_details",
    "unit_prices",
}

_UPPERCASE_TEXT_FIELD_NAMES = {
    "bill_of_lading_number",
    "container_number",
    "currency",
    "groupage_note_number",
    "item_code",
    "loading_id",
    "receipt_number",
    "reference",
}


def _smart_title_token(match):
    token = match.group(0)
    lower_token = token.lower()
    if lower_token in _ACRONYMS:
        return _ACRONYMS[lower_token]
    if len(token) > 1 and token.isupper():
        return token
    return token[:1].upper() + token[1:].lower()


def _smart_title_text(value):
    return re.sub(r"[A-Za-z]+(?:'[A-Za-z]+)?", _smart_title_token, value)


def normalize_text_entry(field_name, value):
    """Normalize user-entered text without touching exact identifiers/passwords."""
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    if not normalized:
        return normalized

    name = (field_name or "").lower()
    if name in _PRESERVE_TEXT_FIELD_NAMES:
        return normalized
    if name == "email" or name.endswith("_email"):
        return normalized.lower()
    if name in _UPPERCASE_TEXT_FIELD_NAMES or name.endswith("_number"):
        return normalized.upper()

    lines = [_smart_title_text(line.strip()) for line in normalized.splitlines()]
    return "\n".join(lines)


class NormalizedTextMixin:
    """Normalize CharField values after each form's own validation runs."""

    def clean(self):
        cleaned_data = super().clean()
        for field_name, value in list(cleaned_data.items()):
            field = self.fields.get(field_name)
            if isinstance(value, str) and isinstance(field, forms.CharField):
                cleaned_data[field_name] = normalize_text_entry(field_name, value)
        return cleaned_data


def _parse_line_items(raw_value):
    """Parse invoice line items from `description,amount[,quantity]` lines."""
    # Accept pasted JSON/Python-list payloads from older UI states, e.g.
    # [{'description': 'Item', 'quantity': '2', 'amount': 120.0}]
    if isinstance(raw_value, list):
        parsed_payload = raw_value
    else:
        raw_text = str(raw_value or "").strip()
        parsed_payload = None
        if raw_text.startswith("[") and raw_text.endswith("]"):
            for parser in (json.loads, ast.literal_eval):
                try:
                    candidate = parser(raw_text)
                    if isinstance(candidate, list):
                        parsed_payload = candidate
                        break
                except Exception:
                    continue

    if parsed_payload is not None:
        items = []
        for index, item in enumerate(parsed_payload, start=1):
            if not isinstance(item, dict):
                raise forms.ValidationError(
                    f"Line {index}: invalid item format in pasted list."
                )
            description = normalize_text_entry(
                "description", str(item.get("description") or item.get("name") or "")
            )
            if not description:
                raise forms.ValidationError(f"Line {index}: description is required.")
            amount_value = item.get("amount", item.get("total"))
            try:
                amount = float(amount_value)
            except (TypeError, ValueError) as exc:
                raise forms.ValidationError(
                    f"Line {index}: amount must be a number."
                ) from exc
            normalized = {"description": description, "amount": amount}
            quantity_value = item.get("quantity")
            if quantity_value not in (None, ""):
                normalized["quantity"] = str(quantity_value)
            items.append(normalized)
        return items

    items = []
    lines = [line.strip() for line in (raw_value or "").splitlines() if line.strip()]
    for index, line in enumerate(lines, start=1):
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 2:
            raise forms.ValidationError(
                f"Line {index}: use `description,amount` format."
            )
        description = normalize_text_entry("description", parts[0])
        if not description:
            raise forms.ValidationError(f"Line {index}: description is required.")
        try:
            amount = float(parts[1])
        except ValueError as exc:
            raise forms.ValidationError(
                f"Line {index}: amount must be a number."
            ) from exc

        item = {"description": description, "amount": amount}
        if len(parts) >= 3 and parts[2]:
            item["quantity"] = parts[2]
        items.append(item)
    return items


def _format_line_items(items):
    """Format stored item list back to editable `description,amount,quantity` lines."""
    lines = []
    if not isinstance(items, list):
        return ""
    for item in items:
        if not isinstance(item, dict):
            continue
        description = str(item.get("description") or item.get("name") or "").strip()
        amount = item.get("amount")
        quantity = item.get("quantity")
        if description and amount is not None:
            line = f"{description},{amount}"
            if quantity not in (None, ""):
                line += f",{quantity}"
            lines.append(line)
    return "\n".join(lines)


def _calculate_items_subtotal(items):
    """Calculate subtotal using amount x quantity when quantity is numeric."""
    subtotal = Decimal("0")
    if not isinstance(items, list):
        return subtotal
    for item in items:
        if not isinstance(item, dict):
            continue
        amount = item.get("amount")
        try:
            line_amount = Decimal(str(amount))
        except (InvalidOperation, TypeError, ValueError):
            continue

        quantity_value = item.get("quantity")
        if quantity_value not in (None, ""):
            try:
                quantity = Decimal(str(quantity_value))
                if quantity > 0:
                    line_amount *= quantity
            except (InvalidOperation, TypeError, ValueError):
                # Keep backward compatibility for non-numeric quantities.
                pass

        subtotal += line_amount
    return subtotal


def _parse_sourcing_items(raw_value):
    """Parse sourcing item details from `name|quantity|unit|notes` lines."""
    items = []
    lines = [line.strip() for line in (raw_value or "").splitlines() if line.strip()]
    for index, line in enumerate(lines, start=1):
        parts = [part.strip() for part in line.split("|")]
        if not parts or not parts[0]:
            raise forms.ValidationError(f"Line {index}: item name is required.")
        item = {"name": normalize_text_entry("name", parts[0])}
        if len(parts) >= 2 and parts[1]:
            item["quantity"] = parts[1]
        if len(parts) >= 3 and parts[2]:
            item["unit"] = normalize_text_entry("unit", parts[2])
        if len(parts) >= 4 and parts[3]:
            item["notes"] = normalize_text_entry("notes", parts[3])
        items.append(item)
    return items


def _format_sourcing_items(items):
    """Format stored sourcing item list back to editable lines."""
    lines = []
    if not isinstance(items, list):
        return ""
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("description") or "").strip()
        quantity = str(item.get("quantity") or "").strip()
        unit = str(item.get("unit") or "").strip()
        notes = str(item.get("notes") or "").strip()
        if name:
            lines.append("|".join([name, quantity, unit, notes]).rstrip("|"))
    return "\n".join(lines)


def _parse_unit_prices(raw_value):
    """Parse pricing lines into a dict using a forgiving best-effort strategy.

    Supported per-line shapes (all optional, never raises):
        item|price          -> {item: price}
        item|price|notes    -> {item: price}  (extra columns ignored)
        item                -> skipped (no price yet)
        <blank>             -> skipped
        item|<non-number>   -> skipped (bad price ignored, never blocks save)

    The original strict parser surfaced confusing errors (e.g. ``Line 1: use
    `item|price` format.``) when users typed free-form notes here. Sourcing
    drafts evolve incrementally, so this field is intentionally lenient now.
    """
    prices = {}
    lines = [line.strip() for line in (raw_value or "").splitlines() if line.strip()]
    for line in lines:
        parts = [part.strip() for part in line.split("|")]
        key = parts[0]
        if not key or len(parts) < 2:
            continue
        try:
            prices[key] = float(parts[1])
        except (TypeError, ValueError):
            # Ignore non-numeric prices rather than rejecting the whole form.
            continue
    return prices


def _format_unit_prices(prices):
    """Format unit price dict back to editable `item|price` lines."""
    if not isinstance(prices, dict):
        return ""
    return "\n".join(f"{key}|{value}" for key, value in prices.items())


def _parse_decimal_or_none(raw_value):
    cleaned_value = str(raw_value or "").strip()
    if not cleaned_value:
        return None
    try:
        return Decimal(cleaned_value)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _build_sourcing_item_rows(items, prices):
    """Normalize sourcing items for layman-friendly per-item capture screens."""
    rows = []
    normalized_prices = prices if isinstance(prices, dict) else {}
    if not isinstance(items, list):
        return rows

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("description") or "").strip()
        if not name:
            continue
        quote_options = item.get("quote_options")
        if not isinstance(quote_options, list):
            quote_options = []

        normalized_quotes = []
        for quote in quote_options[:3]:
            if not isinstance(quote, dict):
                continue
            normalized_quotes.append(
                {
                    "supplier_name": str(quote.get("supplier_name") or "").strip(),
                    "supplier_contact": str(
                        quote.get("supplier_contact") or ""
                    ).strip(),
                    "unit_price": str(quote.get("unit_price") or "").strip(),
                }
            )

        if not normalized_quotes:
            normalized_quotes.append(
                {
                    "supplier_name": str(item.get("supplier_name") or "").strip(),
                    "supplier_contact": str(item.get("supplier_contact") or "").strip(),
                    "unit_price": str(normalized_prices.get(name, "")).strip(),
                }
            )

        while len(normalized_quotes) < 3:
            normalized_quotes.append(
                {"supplier_name": "", "supplier_contact": "", "unit_price": ""}
            )

        quantity_text = str(item.get("quantity") or "1").strip()
        quantity_decimal = _parse_decimal_or_none(quantity_text) or Decimal("1")
        cheapest_quote = ""
        cheapest_price = None
        quote_line_totals = {}

        for quote_index, quote in enumerate(normalized_quotes, start=1):
            quote_price = _parse_decimal_or_none(quote["unit_price"])
            if quote_price is None:
                quote_line_totals[str(quote_index)] = ""
                continue
            quote_line_totals[str(quote_index)] = (
                f"{(quantity_decimal * quote_price):.2f}"
            )
            if cheapest_price is None or quote_price < cheapest_price:
                cheapest_price = quote_price
                cheapest_quote = str(quote_index)

        preferred_quote = str(item.get("preferred_quote") or "").strip()
        if preferred_quote not in {"1", "2", "3"}:
            preferred_quote = cheapest_quote

        rows.append(
            {
                "index": index,
                "name": name,
                "quantity": quantity_text,
                "unit": str(item.get("unit") or "").strip(),
                "notes": str(item.get("notes") or "").strip(),
                "quote_1_supplier_name": normalized_quotes[0]["supplier_name"],
                "quote_1_supplier_contact": normalized_quotes[0]["supplier_contact"],
                "quote_1_unit_price": normalized_quotes[0]["unit_price"],
                "quote_1_line_total": quote_line_totals.get("1", ""),
                "quote_2_supplier_name": normalized_quotes[1]["supplier_name"],
                "quote_2_supplier_contact": normalized_quotes[1]["supplier_contact"],
                "quote_2_unit_price": normalized_quotes[1]["unit_price"],
                "quote_2_line_total": quote_line_totals.get("2", ""),
                "quote_3_supplier_name": normalized_quotes[2]["supplier_name"],
                "quote_3_supplier_contact": normalized_quotes[2]["supplier_contact"],
                "quote_3_unit_price": normalized_quotes[2]["unit_price"],
                "quote_3_line_total": quote_line_totals.get("3", ""),
                "cheapest_quote": cheapest_quote,
                "preferred_quote": preferred_quote,
                "preferred_unit_price": str(normalized_prices.get(name, "")).strip(),
            }
        )
    return rows


from .models import (
    Client,
    Commission,
    ContainerReturn,
    CustomUser,
    Document,
    FinalInvoice,
    FulfillmentLine,
    FulfillmentOrder,
    InventoryItem,
    Loading,
    Payment,
    PaymentTransaction,
    ProformaInvoice,
    ProofOfDelivery,
    PurchaseOrder,
    Receipt,
    Sourcing,
    Supplier,
    SupplierProduct,
    Transaction,
    TransactionPaymentRecord,
    Transit,
    ShipmentLeg,
    SignatureProfile,
)


class UserRegistrationForm(NormalizedTextMixin, UserCreationForm):
    """Form for creating new users"""

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Username"}
        ),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email"})
    )
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "First Name"}
        ),
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Last Name"}
        ),
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Phone Number"}
        ),
    )
    role = forms.ChoiceField(
        choices=CustomUser.ROLE_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Password"}
        ),
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Confirm Password"}
        ),
    )

    class Meta:
        model = CustomUser
        fields = ("username", "email", "first_name", "last_name", "phone", "role")


class SignatureProfileForm(NormalizedTextMixin, forms.ModelForm):
    """Upload or update a user's official document signature."""

    class Meta:
        model = SignatureProfile
        fields = ("signature_image", "title", "is_active")
        widgets = {
            "signature_image": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            ),
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Authorized Signatory",
                }
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_signature_image(self):
        signature_image = self.cleaned_data.get("signature_image")
        if not signature_image:
            return signature_image
        allowed_extensions = (".png", ".jpg", ".jpeg", ".webp")
        if not signature_image.name.lower().endswith(allowed_extensions):
            raise forms.ValidationError(
                "Upload a PNG, JPG, JPEG, or WEBP signature image."
            )
        if signature_image.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Signature image must be 2 MB or smaller.")
        return signature_image


class ClientForm(NormalizedTextMixin, forms.ModelForm):
    """Form for creating and updating clients"""

    @staticmethod
    def _normalize_phone(value):
        return re.sub(r"\D+", "", value or "")

    class Meta:
        model = Client
        fields = (
            "name",
            "company_name",
            "contact_person",
            "phone",
            "email",
            "country",
            "address",
            "remarks",
        )
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Client Name"}
            ),
            "company_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Company (if applicable)",
                }
            ),
            "contact_person": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Contact Person"}
            ),
            "phone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Phone Number"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "Email Address"}
            ),
            "country": forms.Select(attrs={"class": "form-control"}),
            "address": forms.Textarea(
                attrs={"class": "form-control", "placeholder": "Address", "rows": 3}
            ),
            "remarks": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Remarks (optional)",
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["remarks"].required = False

    def clean(self):
        cleaned_data = super().clean()
        name = (cleaned_data.get("name") or "").strip()
        phone = cleaned_data.get("phone") or ""
        normalized_phone = self._normalize_phone(phone)
        if not name or not normalized_phone:
            return cleaned_data

        duplicate_candidates = Client.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            duplicate_candidates = duplicate_candidates.exclude(pk=self.instance.pk)

        duplicate = next(
            (
                client
                for client in duplicate_candidates.only("client_id", "name", "phone")
                if self._normalize_phone(client.phone) == normalized_phone
            ),
            None,
        )
        if duplicate:
            message = (
                f"A client named {duplicate.name} with this phone number already "
                f"exists ({duplicate.client_id}). Review the existing client before saving."
            )
            self.add_error("name", message)
            self.add_error("phone", message)
        return cleaned_data


class LoadingForm(NormalizedTextMixin, forms.ModelForm):
    """Form for creating and updating loadings"""

    class Meta:
        model = Loading
        fields = (
            "entry_type",
            "loading_id",
            "client",
            "loading_date",
            "item_description",
            "packages",
            "weight",
            "cbm",
            "container_number",
            "container_size",
            "warehouse_location",
            "bill_of_lading_number",
            "groupage_note_number",
            "origin",
            "destination",
        )
        widgets = {
            "entry_type": forms.Select(attrs={"class": "form-control"}),
            "loading_id": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Loading ID"}
            ),
            "client": forms.Select(attrs={"class": "form-control"}),
            "loading_date": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "item_description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Item Description",
                    "rows": 3,
                }
            ),
            "packages": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Packages",
                    "min": "1",
                }
            ),
            "weight": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Weight (KG)",
                    "step": "0.01",
                }
            ),
            "cbm": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "CBM",
                    "step": "0.001",
                }
            ),
            "container_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Container Number"}
            ),
            "container_size": forms.Select(attrs={"class": "form-control"}),
            "warehouse_location": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Warehouse"}
            ),
            "bill_of_lading_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Generated on save",
                }
            ),
            "groupage_note_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Generated on save",
                }
            ),
            "origin": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Origin"}
            ),
            "destination": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Destination"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["packages"].required = False
        self.fields["weight"].required = False
        self.fields["cbm"].required = False
        self.fields["container_size"].required = False
        self.fields["container_number"].required = False
        self.fields["client"].empty_label = "Select client"
        self.fields["loading_id"].widget.attrs["readonly"] = True
        self.fields["bill_of_lading_number"].widget.attrs["readonly"] = True
        self.fields["groupage_note_number"].widget.attrs["readonly"] = True

        if not self.instance.pk:
            entry_type = (
                self.data.get("entry_type")
                or self.initial.get("entry_type")
                or "FULL_CONTAINER"
            )
            self.fields["entry_type"].initial = entry_type
            self.fields["loading_id"].initial = Loading.generate_loading_id(entry_type)
            if entry_type == "FULL_CONTAINER":
                self.fields["bill_of_lading_number"].initial = (
                    Loading.generate_bill_of_lading_number()
                )
            if entry_type == "GROUPAGE":
                self.fields["groupage_note_number"].initial = (
                    Loading.generate_groupage_note_number()
                )
        else:
            self.fields["entry_type"].disabled = True

        size_choices = [
            choice for choice in self.fields["container_size"].choices if choice[0]
        ]
        self.fields["container_size"].choices = [
            ("", "Select size (optional)")
        ] + size_choices

    def clean(self):
        cleaned_data = super().clean()
        entry_type = cleaned_data.get("entry_type") or "FULL_CONTAINER"

        if entry_type == "FULL_CONTAINER" and not cleaned_data.get(
            "warehouse_location"
        ):
            self.add_error(
                "warehouse_location",
                "Warehouse is required for full container entries.",
            )

        if entry_type == "FULL_CONTAINER" and not cleaned_data.get("container_number"):
            self.add_error(
                "container_number",
                "Container number is required for full container entries.",
            )

        if entry_type == "GROUPAGE" and not cleaned_data.get("weight"):
            self.add_error("weight", "Weight is required for groupage entries.")

        if entry_type == "GROUPAGE" and not cleaned_data.get("cbm"):
            self.add_error("cbm", "CBM is required for groupage entries.")

        if entry_type == "GROUPAGE" and not cleaned_data.get("packages"):
            self.add_error("packages", "Packages are required for groupage entries.")

        if entry_type == "GROUPAGE" and not cleaned_data.get("warehouse_location"):
            self.add_error(
                "warehouse_location",
                "Warehouse is required for groupage consolidation entries.",
            )

        if not self.instance.pk:
            cleaned_data["loading_id"] = Loading.generate_loading_id(entry_type)
            if entry_type == "FULL_CONTAINER":
                cleaned_data["bill_of_lading_number"] = (
                    Loading.generate_bill_of_lading_number()
                )
                cleaned_data["groupage_note_number"] = None
                cleaned_data["packages"] = None
                cleaned_data["cbm"] = None
            elif entry_type == "GROUPAGE":
                cleaned_data["bill_of_lading_number"] = None
                cleaned_data["groupage_note_number"] = (
                    Loading.generate_groupage_note_number()
                )
            else:
                cleaned_data["bill_of_lading_number"] = None
                cleaned_data["groupage_note_number"] = None
                cleaned_data["packages"] = None
                cleaned_data["cbm"] = None

        if entry_type != "GROUPAGE":
            cleaned_data["packages"] = None
            cleaned_data["cbm"] = None

        return cleaned_data


class TransitForm(NormalizedTextMixin, forms.ModelForm):
    """Form for creating and updating transits"""

    class Meta:
        model = Transit
        fields = (
            "loading",
            "vessel_name",
            "boarding_date",
            "eta_kampala",
            "status",
            "remarks",
        )
        widgets = {
            "loading": forms.Select(attrs={"class": "form-control"}),
            "vessel_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Vessel Name"}
            ),
            "boarding_date": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "eta_kampala": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
            "remarks": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Remarks (optional)",
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["remarks"].required = False


class PaymentForm(NormalizedTextMixin, forms.ModelForm):
    """Form for creating and updating payments"""

    class Meta:
        model = Payment
        fields = (
            "final_invoice",
            "loading",
            "billing_basis",
            "billing_rate",
            "amount_charged",
            "payment_date",
            "payment_method",
            "receipt_number",
        )
        widgets = {
            "final_invoice": forms.Select(attrs={"class": "form-control"}),
            "loading": forms.Select(attrs={"class": "form-control"}),
            "billing_basis": forms.Select(attrs={"class": "form-control"}),
            "billing_rate": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Rate",
                    "step": "0.01",
                }
            ),
            "amount_charged": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Amount Charged",
                    "step": "0.01",
                }
            ),
            "payment_date": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "payment_method": forms.Select(attrs={"class": "form-control"}),
            "receipt_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Receipt Number (optional)",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        current_payment = kwargs.pop("current_payment", None)
        super().__init__(*args, **kwargs)
        self.fields["final_invoice"].required = True
        invoice_queryset = FinalInvoice.objects.select_related(
            "transaction__customer"
        ).order_by("-is_confirmed", "-created_at")

        eligible_client_ids = invoice_queryset.values_list(
            "transaction__customer_id", flat=True
        )
        loading_queryset = Loading.objects.select_related("client").filter(
            client_id__in=eligible_client_ids
        )

        available_loading_queryset = loading_queryset.filter(payment__isnull=True)
        if current_payment and current_payment.loading_id:
            available_loading_queryset = (
                available_loading_queryset
                | Loading.objects.select_related("client").filter(
                    pk=current_payment.loading_id
                )
            ).distinct()

        eligible_client_ids = available_loading_queryset.values_list(
            "client_id", flat=True
        )
        invoice_queryset = invoice_queryset.filter(
            transaction__customer_id__in=eligible_client_ids
        )
        if current_payment and current_payment.final_invoice_id:
            invoice_queryset = (
                invoice_queryset
                | FinalInvoice.objects.select_related("transaction__customer").filter(
                    pk=current_payment.final_invoice_id
                )
            ).distinct()

        self.fields["loading"].queryset = available_loading_queryset.order_by(
            "-created_at"
        )
        self.fields["final_invoice"].queryset = invoice_queryset.order_by(
            "-is_confirmed", "-created_at"
        )
        self.fields["final_invoice"].empty_label = "Select invoice"
        self.fields["billing_rate"].required = False
        self.fields["amount_charged"].help_text = (
            "For groupage, select Weight (KG) or CBM to auto-calculate from the loading record."
        )

    def clean(self):
        cleaned_data = super().clean()
        final_invoice = cleaned_data.get("final_invoice")
        loading = cleaned_data.get("loading")
        billing_basis = cleaned_data.get("billing_basis") or "manual"
        billing_rate = cleaned_data.get("billing_rate")
        amount_charged = cleaned_data.get("amount_charged")

        if not final_invoice:
            self.add_error("final_invoice", "Payment must be attached to an invoice.")

        if not loading:
            return cleaned_data

        if not FinalInvoice.objects.filter(
            transaction__customer_id=loading.client_id
        ).exists():
            self.add_error(
                "loading",
                "No final invoice exists for the selected cargo client.",
            )
            return cleaned_data

        if final_invoice and loading.client_id != final_invoice.transaction.customer_id:
            self.add_error(
                "loading",
                "Selected loading client must match the client on the attached invoice.",
            )

        if loading.entry_type != "GROUPAGE":
            cleaned_data["billing_basis"] = "manual"
            cleaned_data["billing_rate"] = None
            return cleaned_data

        if billing_basis in {"kg", "cbm"}:
            if billing_rate is None:
                self.add_error(
                    "billing_rate", "Rate is required when charging by KG or CBM."
                )
                return cleaned_data
            quantity = loading.weight if billing_basis == "kg" else loading.cbm
            if quantity is None:
                unit_label = "weight" if billing_basis == "kg" else "CBM"
                self.add_error(
                    "billing_basis",
                    f"This loading has no {unit_label} recorded for groupage charging.",
                )
                return cleaned_data
            cleaned_data["amount_charged"] = quantity * billing_rate
        else:
            cleaned_data["billing_rate"] = None

        if billing_basis == "manual" and amount_charged is None:
            self.add_error(
                "amount_charged", "Amount charged is required for manual billing."
            )

        return cleaned_data


class PaymentTransactionForm(NormalizedTextMixin, forms.ModelForm):
    """Form for recording individual payment events"""

    class Meta:
        model = PaymentTransaction
        fields = ("amount", "payment_date", "payment_method", "reference", "notes")
        widgets = {
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Amount Received",
                    "step": "0.01",
                }
            ),
            "payment_date": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "payment_method": forms.Select(attrs={"class": "form-control"}),
            "reference": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Entry Number / Reference",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Optional notes",
                    "rows": 3,
                }
            ),
        }


class ContainerReturnForm(NormalizedTextMixin, forms.ModelForm):
    """Form for creating and updating container returns"""

    class Meta:
        model = ContainerReturn
        fields = (
            "container_number",
            "container_size",
            "loading",
            "return_date",
            "condition",
            "status",
            "remarks",
        )
        widgets = {
            "container_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Container Number"}
            ),
            "container_size": forms.Select(attrs={"class": "form-control"}),
            "loading": forms.Select(attrs={"class": "form-control"}),
            "return_date": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "condition": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "remarks": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Remarks (optional)",
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["container_size"].required = False
        self.fields["remarks"].required = False

    def clean(self):
        cleaned_data = super().clean()
        container_number = cleaned_data.get("container_number")
        loading = cleaned_data.get("loading")
        if container_number and loading:
            duplicate = ContainerReturn.objects.filter(
                loading=loading,
                container_number__iexact=container_number,
            )
            if self.instance and self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            existing_return = duplicate.first()
            if existing_return:
                self.add_error(
                    "container_number",
                    "This container return has already been captured for the selected loading.",
                )
                self.add_error(
                    "loading",
                    f"Existing return record: {existing_return.container_number} on {existing_return.return_date:%Y-%m-%d}.",
                )
        return cleaned_data


class TransactionForm(NormalizedTextMixin, forms.ModelForm):
    """Form for creating and updating core transactions."""

    class Meta:
        model = Transaction
        fields = ("customer", "status", "description", "notes", "estimated_delivery")
        widgets = {
            "customer": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Goods/service description",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Internal notes",
                }
            ),
            "estimated_delivery": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
        }


class DocumentForm(forms.ModelForm):
    """Form for attaching documents to transactions."""

    class Meta:
        model = Document
        fields = ("document_type", "original_file", "processed_file")
        widgets = {
            "document_type": forms.Select(attrs={"class": "form-control"}),
            "original_file": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "processed_file": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class SourcingForm(NormalizedTextMixin, forms.ModelForm):
    """Form for overseas sourcing records."""

    item_details = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 6,
                "placeholder": "Item Name|Quantity|Unit|Notes (one item per line)\ne.g. King-size Beds|10|PCS|Durable frames",
                "style": "font-family:'Courier New',monospace;",
                "spellcheck": "false",
            }
        ),
        help_text="Format: Item Name|Quantity|Unit|Notes (one line per item).",
    )
    unit_prices = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 6,
                "placeholder": "Item Name|Unit Price (one per line)\ne.g. King-size Beds|450.00",
                "style": "font-family:'Courier New',monospace;",
                "spellcheck": "false",
            }
        ),
        help_text="Format: Item Name|Unit Price (one line per item).",
    )
    validity_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        help_text="Proforma validity date. Used when auto-generating the proforma invoice.",
    )

    class Meta:
        model = Sourcing
        fields = (
            "transaction",
            "supplier_name",
            "supplier_contact",
            "item_details",
            "unit_prices",
            "notes",
        )
        widgets = {
            "transaction": forms.Select(attrs={"class": "form-control"}),
            "supplier_name": forms.TextInput(attrs={"class": "form-control"}),
            "supplier_contact": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier_name"].required = False
        self.fields["supplier_contact"].required = False
        if self.instance and self.instance.pk:
            self.fields["item_details"].initial = _format_sourcing_items(
                self.instance.item_details
            )
            self.fields["unit_prices"].initial = _format_unit_prices(
                self.instance.unit_prices
            )
        if self.is_bound:
            self.item_rows = self._build_item_rows_from_post()
        else:
            initial_items = None
            initial_prices = None
            if self.instance and self.instance.pk:
                initial_items = self.instance.item_details
                initial_prices = self.instance.unit_prices
            else:
                initial_items = _parse_sourcing_items(
                    self.initial.get("item_details", "")
                )
                try:
                    initial_prices = _parse_unit_prices(
                        self.initial.get("unit_prices", "")
                    )
                except forms.ValidationError:
                    # Keep the worksheet renderable even if legacy text payloads are malformed.
                    initial_prices = {}
            self.item_rows = _build_sourcing_item_rows(initial_items, initial_prices)

    def _build_item_rows_from_post(self):
        item_names = self.data.getlist("item_name[]")
        item_quantities = self.data.getlist("item_quantity[]")
        item_units = self.data.getlist("item_unit[]")
        item_notes = self.data.getlist("item_notes[]")
        quote_1_suppliers = self.data.getlist("item_quote_1_supplier_name[]")
        quote_1_contacts = self.data.getlist("item_quote_1_supplier_contact[]")
        quote_1_prices = self.data.getlist("item_quote_1_unit_price[]")
        quote_2_suppliers = self.data.getlist("item_quote_2_supplier_name[]")
        quote_2_contacts = self.data.getlist("item_quote_2_supplier_contact[]")
        quote_2_prices = self.data.getlist("item_quote_2_unit_price[]")
        quote_3_suppliers = self.data.getlist("item_quote_3_supplier_name[]")
        quote_3_contacts = self.data.getlist("item_quote_3_supplier_contact[]")
        quote_3_prices = self.data.getlist("item_quote_3_unit_price[]")
        preferred_quotes = self.data.getlist("item_preferred_quote[]")

        if not item_names:
            try:
                fallback_items = _parse_sourcing_items(
                    self.data.get("item_details", "")
                )
            except forms.ValidationError:
                fallback_items = []
            try:
                fallback_prices = _parse_unit_prices(self.data.get("unit_prices", ""))
            except forms.ValidationError:
                fallback_prices = {}
            return _build_sourcing_item_rows(
                fallback_items,
                fallback_prices,
            )

        rows = []
        for index, name in enumerate(item_names, start=1):
            cleaned_name = str(name or "").strip()
            if not cleaned_name:
                continue
            rows.append(
                {
                    "index": index,
                    "name": cleaned_name,
                    "quantity": str(item_quantities[index - 1] or "1").strip(),
                    "unit": str(item_units[index - 1] or "").strip(),
                    "notes": str(item_notes[index - 1] or "").strip(),
                    "quote_1_supplier_name": str(
                        quote_1_suppliers[index - 1] or ""
                    ).strip(),
                    "quote_1_supplier_contact": str(
                        quote_1_contacts[index - 1] or ""
                    ).strip(),
                    "quote_1_unit_price": str(quote_1_prices[index - 1] or "").strip(),
                    "quote_2_supplier_name": str(
                        quote_2_suppliers[index - 1] or ""
                    ).strip(),
                    "quote_2_supplier_contact": str(
                        quote_2_contacts[index - 1] or ""
                    ).strip(),
                    "quote_2_unit_price": str(quote_2_prices[index - 1] or "").strip(),
                    "quote_3_supplier_name": str(
                        quote_3_suppliers[index - 1] or ""
                    ).strip(),
                    "quote_3_supplier_contact": str(
                        quote_3_contacts[index - 1] or ""
                    ).strip(),
                    "quote_3_unit_price": str(quote_3_prices[index - 1] or "").strip(),
                    "preferred_quote": str(preferred_quotes[index - 1] or "").strip(),
                }
            )
        return rows

    def clean_item_details(self):
        item_names = self.data.getlist("item_name[]")
        if not item_names:
            return _parse_sourcing_items(self.cleaned_data.get("item_details"))

        item_quantities = self.data.getlist("item_quantity[]")
        item_units = self.data.getlist("item_unit[]")
        item_notes = self.data.getlist("item_notes[]")
        quote_supplier_names = [
            self.data.getlist("item_quote_1_supplier_name[]"),
            self.data.getlist("item_quote_2_supplier_name[]"),
            self.data.getlist("item_quote_3_supplier_name[]"),
        ]
        quote_supplier_contacts = [
            self.data.getlist("item_quote_1_supplier_contact[]"),
            self.data.getlist("item_quote_2_supplier_contact[]"),
            self.data.getlist("item_quote_3_supplier_contact[]"),
        ]
        quote_unit_prices = [
            self.data.getlist("item_quote_1_unit_price[]"),
            self.data.getlist("item_quote_2_unit_price[]"),
            self.data.getlist("item_quote_3_unit_price[]"),
        ]
        preferred_quotes = self.data.getlist("item_preferred_quote[]")

        items = []
        for index, name in enumerate(item_names, start=1):
            cleaned_name = str(name or "").strip()
            if not cleaned_name:
                raise forms.ValidationError(f"Item {index}: item name is required.")
            item = {"name": cleaned_name}
            quantity = str(item_quantities[index - 1] or "").strip()
            unit = str(item_units[index - 1] or "").strip()
            notes = str(item_notes[index - 1] or "").strip()
            if quantity:
                item["quantity"] = quantity
            if unit:
                item["unit"] = unit
            if notes:
                item["notes"] = notes

            quote_options = []
            for quote_index in range(3):
                supplier_name = str(
                    quote_supplier_names[quote_index][index - 1] or ""
                ).strip()
                supplier_contact = str(
                    quote_supplier_contacts[quote_index][index - 1] or ""
                ).strip()
                unit_price = str(
                    quote_unit_prices[quote_index][index - 1] or ""
                ).strip()

                if not supplier_name and not supplier_contact and not unit_price:
                    continue

                quote = {}
                if supplier_name:
                    quote["supplier_name"] = supplier_name
                if supplier_contact:
                    quote["supplier_contact"] = supplier_contact
                if unit_price:
                    quote["unit_price"] = unit_price
                quote_options.append(quote)

            if quote_options:
                item["quote_options"] = quote_options
                first_quote = quote_options[0]
                if first_quote.get("supplier_name"):
                    item["supplier_name"] = first_quote["supplier_name"]
                if first_quote.get("supplier_contact"):
                    item["supplier_contact"] = first_quote["supplier_contact"]
            preferred_quote = str(preferred_quotes[index - 1] or "").strip()
            if preferred_quote in {"1", "2", "3"}:
                item["preferred_quote"] = preferred_quote
            items.append(item)
        return items

    def clean_unit_prices(self):
        item_names = self.data.getlist("item_name[]")
        if not item_names:
            return _parse_unit_prices(self.cleaned_data.get("unit_prices"))

        quote_price_columns = [
            self.data.getlist("item_quote_1_unit_price[]"),
            self.data.getlist("item_quote_2_unit_price[]"),
            self.data.getlist("item_quote_3_unit_price[]"),
        ]
        preferred_quotes = self.data.getlist("item_preferred_quote[]")

        prices = {}
        for index, name in enumerate(item_names, start=1):
            cleaned_name = str(name or "").strip()
            if not cleaned_name:
                continue

            parsed_prices = {}
            for quote_index, quote_prices in enumerate(quote_price_columns, start=1):
                cleaned_price = str(quote_prices[index - 1] or "").strip()
                if not cleaned_price:
                    continue
                try:
                    parsed_prices[str(quote_index)] = float(cleaned_price)
                except ValueError as exc:
                    raise forms.ValidationError(
                        f"Item {index}, quote {quote_index}: unit price must be a number."
                    ) from exc

            preferred_quote = str(preferred_quotes[index - 1] or "").strip()
            if preferred_quote in parsed_prices:
                prices[cleaned_name] = parsed_prices[preferred_quote]
            elif parsed_prices:
                prices[cleaned_name] = min(parsed_prices.values())
        return prices

    def clean(self):
        cleaned_data = super().clean()
        items = cleaned_data.get("item_details") or []
        typed_supplier = str(cleaned_data.get("supplier_name") or "").strip()
        typed_contact = str(cleaned_data.get("supplier_contact") or "").strip()

        supplier_names = []
        supplier_contacts = []
        for item in items:
            if not isinstance(item, dict):
                continue
            preferred_quote = str(item.get("preferred_quote") or "").strip()
            quote_options = item.get("quote_options")
            if isinstance(quote_options, list):
                if preferred_quote in {"1", "2", "3"}:
                    preferred_index = int(preferred_quote) - 1
                    if preferred_index < len(quote_options):
                        preferred_option = quote_options[preferred_index]
                        if isinstance(preferred_option, dict):
                            item_supplier = str(
                                preferred_option.get("supplier_name") or ""
                            ).strip()
                            item_contact = str(
                                preferred_option.get("supplier_contact") or ""
                            ).strip()
                            if item_supplier and item_supplier not in supplier_names:
                                supplier_names.append(item_supplier)
                            if item_contact and item_contact not in supplier_contacts:
                                supplier_contacts.append(item_contact)
                for quote in quote_options:
                    if not isinstance(quote, dict):
                        continue
                    item_supplier = str(quote.get("supplier_name") or "").strip()
                    item_contact = str(quote.get("supplier_contact") or "").strip()
                    if item_supplier and item_supplier not in supplier_names:
                        supplier_names.append(item_supplier)
                    if item_contact and item_contact not in supplier_contacts:
                        supplier_contacts.append(item_contact)
            else:
                item_supplier = str(item.get("supplier_name") or "").strip()
                item_contact = str(item.get("supplier_contact") or "").strip()
                if item_supplier and item_supplier not in supplier_names:
                    supplier_names.append(item_supplier)
                if item_contact and item_contact not in supplier_contacts:
                    supplier_contacts.append(item_contact)

        if typed_supplier:
            cleaned_data["supplier_name"] = typed_supplier
        elif len(supplier_names) == 1:
            cleaned_data["supplier_name"] = supplier_names[0]
        elif len(supplier_names) > 1:
            cleaned_data["supplier_name"] = "Multiple suppliers"
        else:
            cleaned_data["supplier_name"] = "Pending supplier pricing"

        if typed_contact:
            cleaned_data["supplier_contact"] = typed_contact
        elif len(supplier_contacts) == 1:
            cleaned_data["supplier_contact"] = supplier_contacts[0]
        elif len(supplier_contacts) > 1:
            cleaned_data["supplier_contact"] = "Multiple contacts"
        else:
            cleaned_data["supplier_contact"] = ""

        return cleaned_data


class ProformaInvoiceForm(NormalizedTextMixin, forms.ModelForm):
    """Form for proforma invoice creation."""

    items = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 7,
                "placeholder": "e.g. Laptop Charger,45.00,2\nOffice Chair,120.00\nUSB Cable,8.50,10",
                "style": "font-family: 'Courier New', monospace;",
                "spellcheck": "false",
            }
        ),
        help_text="Enter one line per item: Description,Amount,Quantity (quantity optional).",
    )

    class Meta:
        model = ProformaInvoice
        fields = ("transaction", "items", "subtotal", "validity_date", "status")
        widgets = {
            "transaction": forms.Select(attrs={"class": "form-control"}),
            "subtotal": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "validity_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subtotal"].required = False
        self.fields["subtotal"].widget.attrs["readonly"] = "readonly"
        self.fields["subtotal"].help_text = "Automatically calculated from item lines."
        if self.instance and self.instance.pk:
            self.fields["items"].initial = _format_line_items(self.instance.items)

    def clean_items(self):
        return _parse_line_items(self.cleaned_data.get("items"))

    def clean(self):
        cleaned_data = super().clean()
        items = cleaned_data.get("items")
        if items is not None:
            cleaned_data["subtotal"] = _calculate_items_subtotal(items)
        return cleaned_data


class FinalInvoiceForm(NormalizedTextMixin, forms.ModelForm):
    """Form for final invoice creation and confirmation."""

    items = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 7,
                "placeholder": "e.g. Laptop Charger,45.00,2\nOffice Chair,120.00\nUSB Cable,8.50,10",
                "style": "font-family: 'Courier New', monospace;",
                "spellcheck": "false",
            }
        ),
        help_text="Enter one line per item: Description,Amount,Quantity (quantity optional).",
    )

    class Meta:
        model = FinalInvoice
        fields = (
            "transaction",
            "items",
            "subtotal",
            "shipping_cost",
            "service_fee",
            "currency",
            "shipping_mode",
            "route",
            "is_confirmed",
        )
        widgets = {
            "transaction": forms.Select(attrs={"class": "form-control"}),
            "subtotal": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "shipping_cost": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "service_fee": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "currency": forms.TextInput(attrs={"class": "form-control"}),
            "shipping_mode": forms.Select(attrs={"class": "form-control"}),
            "route": forms.TextInput(attrs={"class": "form-control"}),
            "is_confirmed": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subtotal"].required = False
        self.fields["subtotal"].widget.attrs["readonly"] = "readonly"
        self.fields["subtotal"].help_text = "Automatically calculated from item lines."
        if self.instance and self.instance.pk:
            self.fields["items"].initial = _format_line_items(self.instance.items)

    def clean_items(self):
        return _parse_line_items(self.cleaned_data.get("items"))

    def clean(self):
        cleaned_data = super().clean()
        items = cleaned_data.get("items")
        if items is not None:
            cleaned_data["subtotal"] = _calculate_items_subtotal(items)
        return cleaned_data


class SupplierForm(NormalizedTextMixin, forms.ModelForm):
    class Meta:
        model = Supplier
        fields = (
            "name",
            "contact_person",
            "phone",
            "email",
            "address",
            "supplies",
            "notes",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "contact_person": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "supplies": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "e.g. Office chairs, desks, conference tables",
                }
            ),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class SupplierProductForm(NormalizedTextMixin, forms.ModelForm):
    class Meta:
        model = SupplierProduct
        fields = (
            "product_name",
            "specifications",
            "min_order_quantity",
            "unit_price",
            "resale_price",
            "notes",
        )
        widgets = {
            "product_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. Office Chair"}
            ),
            "specifications": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "e.g. Fabric, high-back, 5-star base, adjustable height",
                }
            ),
            "min_order_quantity": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "unit_price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "resale_price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "notes": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Optional notes"}
            ),
        }


class InventoryItemForm(NormalizedTextMixin, forms.ModelForm):
    transaction = forms.ModelChoiceField(
        queryset=Transaction.objects.select_related("customer").order_by("-created_at"),
        widget=forms.Select(attrs={"class": "form-control"}),
        required=True,
    )

    class Meta:
        model = InventoryItem
        fields = (
            "item_code",
            "item_name",
            "description",
            "quantity_purchased",
            "quantity_shipped",
            "transaction",
            "supplier",
        )
        widgets = {
            "item_code": forms.TextInput(attrs={"class": "form-control"}),
            "item_name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "quantity_purchased": forms.NumberInput(attrs={"class": "form-control"}),
            "quantity_shipped": forms.NumberInput(attrs={"class": "form-control"}),
            "supplier": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["transaction"].label_from_instance = (
            lambda tx: f"{tx.customer.name} - {tx.transaction_id}"
        )

    def clean_transaction(self):
        transaction = self.cleaned_data.get("transaction")
        if not transaction:
            raise forms.ValidationError(
                "Select the owner transaction for this warehouse stock item."
            )
        return transaction


class FulfillmentOrderForm(NormalizedTextMixin, forms.ModelForm):
    class Meta:
        model = FulfillmentOrder
        fields = (
            "final_invoice",
            "requires_warehouse_handling",
            "status",
            "warehouse_received_at",
            "warehouse_notes",
            "port_of_loading",
            "destination_port",
            "inland_destination",
            "consignee",
            "planned_dispatch_date",
            "planned_delivery_date",
            "actual_delivery_date",
        )
        widgets = {
            "final_invoice": forms.Select(attrs={"class": "form-control"}),
            "requires_warehouse_handling": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
            "warehouse_received_at": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "warehouse_notes": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "port_of_loading": forms.TextInput(attrs={"class": "form-control"}),
            "destination_port": forms.TextInput(attrs={"class": "form-control"}),
            "inland_destination": forms.TextInput(attrs={"class": "form-control"}),
            "consignee": forms.TextInput(attrs={"class": "form-control"}),
            "planned_dispatch_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "planned_delivery_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "actual_delivery_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
        }

    def __init__(self, *args, transaction=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.transaction = transaction or getattr(self.instance, "transaction", None)
        queryset = FinalInvoice.objects.select_related(
            "transaction__customer"
        ).prefetch_related(
            "payment_records__receipt", "transaction__payment_records__receipt"
        )
        if self.transaction is not None:
            queryset = queryset.filter(transaction=self.transaction)

        invoice_labels = {}
        paid_invoice_ids = []
        for invoice in queryset.order_by("-created_at"):
            invoice_payments = list(invoice.payment_records.all())
            total_paid = sum((payment.amount or 0) for payment in invoice_payments)
            if total_paid <= 0:
                # Backward compatibility for older payment rows not linked to final_invoice.
                invoice_payments = list(invoice.transaction.payment_records.all())
                total_paid = sum((payment.amount or 0) for payment in invoice_payments)

            receipt_numbers = []
            for payment in invoice_payments:
                receipt = getattr(payment, "receipt", None)
                if receipt and receipt.receipt_number:
                    receipt_numbers.append(receipt.receipt_number)
            receipt_numbers = sorted(set(receipt_numbers))
            receipt_text = (
                ", ".join(receipt_numbers) if receipt_numbers else "No Receipt"
            )

            invoice_labels[invoice.pk] = (
                f"FI-{invoice.pk} - {invoice.transaction.customer.name} - "
                f"{invoice.transaction.transaction_id} | Receipt: {receipt_text}"
            )

            if total_paid >= (invoice.total_amount or 0):
                paid_invoice_ids.append(invoice.pk)
        self.fields["final_invoice"].queryset = queryset.filter(
            pk__in=paid_invoice_ids
        ).order_by("-created_at")
        self.fields["final_invoice"].required = True
        self.fields["final_invoice"].label_from_instance = (
            lambda invoice: invoice_labels.get(
                invoice.pk,
                f"FI-{invoice.pk} - {invoice.transaction.customer.name} - {invoice.transaction.transaction_id}",
            )
        )

    def clean_final_invoice(self):
        invoice = self.cleaned_data.get("final_invoice")
        if not invoice:
            raise forms.ValidationError("Select a fully paid final invoice.")
        total_paid = (
            invoice.payment_records.aggregate(total=Sum("amount"))["total"] or 0
        )
        if total_paid <= 0:
            total_paid = (
                invoice.transaction.payment_records.aggregate(total=Sum("amount"))[
                    "total"
                ]
                or 0
            )
        if total_paid < (invoice.total_amount or 0):
            raise forms.ValidationError(
                "Only fully paid final invoices can be used for fulfillment."
            )
        return invoice


class FulfillmentLineForm(NormalizedTextMixin, forms.ModelForm):
    class Meta:
        model = FulfillmentLine
        fields = (
            "inventory_item",
            "quantity_allocated",
            "quantity_dispatched",
            "quantity_delivered",
            "notes",
        )
        widgets = {
            "inventory_item": forms.Select(attrs={"class": "form-control"}),
            "quantity_allocated": forms.NumberInput(attrs={"class": "form-control"}),
            "quantity_dispatched": forms.NumberInput(attrs={"class": "form-control"}),
            "quantity_delivered": forms.NumberInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, order=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.order = order or getattr(self.instance, "order", None)
        queryset = InventoryItem.objects.select_related(
            "transaction__customer", "supplier"
        )
        if self.order is not None:
            queryset = queryset.filter(transaction=self.order.transaction)
        self.fields["inventory_item"].queryset = queryset.order_by("item_name")
        self.fields["inventory_item"].label_from_instance = (
            lambda item: f"{item.item_code} - {item.item_name} (available {item.available_quantity})"
        )


class ShipmentLegForm(NormalizedTextMixin, forms.ModelForm):
    class Meta:
        model = ShipmentLeg
        fields = (
            "sequence",
            "leg_type",
            "origin",
            "destination",
            "carrier",
            "vehicle_or_vessel",
            "departure_date",
            "arrival_eta",
            "actual_arrival",
            "status",
            "notes",
        )
        widgets = {
            "sequence": forms.NumberInput(attrs={"class": "form-control"}),
            "leg_type": forms.Select(attrs={"class": "form-control"}),
            "origin": forms.TextInput(attrs={"class": "form-control"}),
            "destination": forms.TextInput(attrs={"class": "form-control"}),
            "carrier": forms.TextInput(attrs={"class": "form-control"}),
            "vehicle_or_vessel": forms.TextInput(attrs={"class": "form-control"}),
            "departure_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "arrival_eta": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "actual_arrival": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class TransactionPaymentRecordForm(NormalizedTextMixin, forms.ModelForm):
    """Form for recording payments against a sourcing transaction invoice."""

    CURRENCY_CHOICES = (
        ("USD", "USD - US Dollar"),
        ("UGX", "UGX - Uganda Shilling"),
        ("KES", "KES - Kenyan Shilling"),
        ("TZS", "TZS - Tanzanian Shilling"),
        ("EUR", "EUR - Euro"),
        ("GBP", "GBP - British Pound"),
    )

    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = TransactionPaymentRecord
        fields = (
            "transaction",
            "final_invoice",
            "amount_due_snapshot",
            "is_full_payment",
            "amount",
            "currency",
            "cash_received",
            "change_given",
            "balance_after",
            "payment_date",
            "payment_method",
            "reference",
            "notes",
        )
        widgets = {
            "transaction": forms.Select(attrs={"class": "form-control"}),
            "final_invoice": forms.Select(attrs={"class": "form-control"}),
            "amount_due_snapshot": forms.NumberInput(
                attrs={"class": "form-control", "readonly": "readonly", "step": "0.01"}
            ),
            "is_full_payment": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "cash_received": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "change_given": forms.NumberInput(
                attrs={"class": "form-control", "readonly": "readonly", "step": "0.01"}
            ),
            "balance_after": forms.NumberInput(
                attrs={"class": "form-control", "readonly": "readonly", "step": "0.01"}
            ),
            "payment_date": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "payment_method": forms.Select(attrs={"class": "form-control"}),
            "reference": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["transaction"].queryset = Transaction.objects.select_related(
            "customer"
        ).order_by("customer__name", "-created_at")
        self.fields["final_invoice"].queryset = (
            FinalInvoice.objects.all()
            .select_related("transaction")
            .order_by("-is_confirmed", "-created_at")
        )

        selected_transaction_id = None
        if self.is_bound:
            selected_transaction_id = self.data.get("transaction")
        else:
            initial_tx = self.initial.get("transaction")
            if initial_tx is not None:
                selected_transaction_id = (
                    initial_tx.pk if hasattr(initial_tx, "pk") else initial_tx
                )
            elif self.instance.pk:
                selected_transaction_id = self.instance.transaction_id

        try:
            selected_transaction_id = int(selected_transaction_id)
        except (TypeError, ValueError):
            selected_transaction_id = None

        if selected_transaction_id:
            scoped_invoices = FinalInvoice.objects.filter(
                transaction_id=selected_transaction_id,
            ).order_by("-is_confirmed", "-created_at")
            self.fields["final_invoice"].queryset = scoped_invoices
            if not self.is_bound and not self.initial.get("final_invoice"):
                self.initial["final_invoice"] = scoped_invoices.first()

        self.fields["transaction"].label_from_instance = (
            lambda tx: f"{tx.customer.name} - {tx.transaction_id}"
        )
        self.fields["amount_due_snapshot"].label = "Amount Due"
        self.fields["amount"].label = "Payment Amount"
        self.fields["cash_received"].label = "Cash Given In"
        self.fields["change_given"].label = "Change To Return"
        self.fields["balance_after"].label = "Balance After Payment"
        self.fields["is_full_payment"].label = "Full Payment"

    def clean(self):
        cleaned_data = super().clean()
        transaction = cleaned_data.get("transaction")
        final_invoice = cleaned_data.get("final_invoice")
        amount = cleaned_data.get("amount") or Decimal("0")
        is_full_payment = cleaned_data.get("is_full_payment")
        payment_method = cleaned_data.get("payment_method")
        cash_received = cleaned_data.get("cash_received")

        if not transaction:
            return cleaned_data

        invoice = (
            final_invoice
            or transaction.final_invoices.order_by(
                "-is_confirmed", "-created_at"
            ).first()
        )
        if not invoice:
            raise forms.ValidationError(
                "A confirmed invoice is required before recording a trade payment."
            )

        cleaned_data["final_invoice"] = invoice
        prior_paid = transaction.payment_records.exclude(pk=self.instance.pk).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")
        amount_due = max(Decimal(str(invoice.total_amount)) - prior_paid, Decimal("0"))
        cleaned_data["amount_due_snapshot"] = amount_due

        if amount_due <= 0:
            raise forms.ValidationError("This invoice has already been fully paid.")

        if is_full_payment:
            amount = amount_due
            cleaned_data["amount"] = amount_due

        if amount <= 0:
            self.add_error("amount", "Enter the amount being paid.")

        if amount > amount_due:
            self.add_error("amount", "Payment amount cannot exceed the amount due.")

        balance_after = max(amount_due - amount, Decimal("0"))
        cleaned_data["balance_after"] = balance_after

        if payment_method == "cash":
            if cash_received in (None, ""):
                self.add_error(
                    "cash_received", "Enter the cash given in by the client."
                )
            elif cash_received < amount:
                self.add_error(
                    "cash_received",
                    "Cash received cannot be less than the payment amount.",
                )
            else:
                cleaned_data["change_given"] = cash_received - amount
        else:
            cleaned_data["cash_received"] = None
            cleaned_data["change_given"] = Decimal("0")

        return cleaned_data


class CommissionForm(NormalizedTextMixin, forms.ModelForm):
    """Form for capturing commission earned per client."""

    class Meta:
        model = Commission
        fields = ("client", "amount", "currency", "date", "notes")
        widgets = {
            "client": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "e.g. 500.00",
                }
            ),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Optional notes (deal reference, payout method, etc.)",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = Client.objects.order_by("name")
        self.fields["client"].label_from_instance = (
            lambda obj: f"{obj.name} ({obj.client_id})"
        )

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is None:
            return amount
        if amount <= 0:
            raise forms.ValidationError("Commission amount must be greater than zero.")
        return amount


class ProofOfDeliveryForm(NormalizedTextMixin, forms.ModelForm):
    """Capture POD details for either a Loading or a FulfillmentOrder.

    The two FK fields are hidden from the UI: the view that instantiates the
    form pre-binds exactly one of them based on the URL.
    """

    class Meta:
        model = ProofOfDelivery
        fields = (
            "delivered_at",
            "received_by_name",
            "received_by_phone",
            "delivery_address",
            "signature_or_photo",
            "gps_lat",
            "gps_lng",
            "notes",
        )
        widgets = {
            "delivered_at": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "received_by_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Full name"}
            ),
            "received_by_phone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Phone (optional)"}
            ),
            "delivery_address": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Place / address"}
            ),
            "signature_or_photo": forms.ClearableFileInput(
                attrs={"class": "form-control"}
            ),
            "gps_lat": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "any",
                    "placeholder": "0.000000",
                }
            ),
            "gps_lng": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "any",
                    "placeholder": "0.000000",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Optional notes",
                }
            ),
        }
        input_formats = {"delivered_at": ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"]}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["delivered_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
        ]


class SupplierPaymentForm(NormalizedTextMixin, forms.ModelForm):
    class Meta:
        from .models import SupplierPayment

        model = SupplierPayment
        fields = (
            "supplier_name",
            "amount",
            "currency",
            "method",
            "reference",
            "paid_at",
            "notes",
        )
        widgets = {
            "supplier_name": forms.TextInput(attrs={"class": "form-control"}),
            "amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0.01"}
            ),
            "currency": forms.TextInput(attrs={"class": "form-control"}),
            "method": forms.Select(attrs={"class": "form-select"}),
            "reference": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Bank ref / receipt no."}
            ),
            "paid_at": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }
        input_formats = {"paid_at": ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"]}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["paid_at"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"]
