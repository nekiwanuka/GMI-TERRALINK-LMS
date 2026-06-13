from io import BytesIO
from decimal import Decimal
import re
import shutil
import tempfile
from unittest.mock import patch

from django.apps import apps
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from reportlab.pdfgen import canvas

from logistics.models import (
    Client,
    Commission,
    ContainerReturn,
    CustomUser,
    Document,
    DocumentArchive,
    DocumentSignature,
    FinalInvoice,
    GeneralInvoice,
    GeneralPayment,
    GeneralQuotation,
    GeneralReceipt,
    Loading,
    PurchaseOrder,
    ProformaInvoice,
    Receipt,
    SignatureProfile,
    Sourcing,
    SupplierPayment,
    Transaction,
    TransactionPaymentRecord,
)
from logistics.views import (
    _can_manage_general_documents,
    _can_switch_lane,
    _extract_text_from_file,
    _final_invoice_payment_snapshot,
    _has_extractable_document_text,
)
from logistics.role_permissions import role_has_procurement_permissions


class AdminCoverageTests(SimpleTestCase):
    def test_all_logistics_models_are_registered_in_admin(self):
        missing_models = [
            model.__name__
            for model in apps.get_app_config("logistics").get_models()
            if model not in admin.site._registry
        ]

        self.assertEqual(missing_models, [])


class DocumentExtractionTests(SimpleTestCase):
    def test_txt_extraction_rewinds_uploaded_file(self):
        upload = SimpleUploadedFile(
            "purchase-inquiry.txt",
            b"Subject: Test PI\n- Solar battery\n",
            content_type="text/plain",
        )

        text = _extract_text_from_file(upload)

        self.assertIn("Subject: Test PI", text)
        self.assertEqual(upload.tell(), 0)
        self.assertTrue(_has_extractable_document_text(text))

    def test_pdf_extraction_returns_text(self):
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer)
        pdf.drawString(72, 720, "Subject: Generator quotation")
        pdf.drawString(72, 700, "- Diesel generator")
        pdf.save()
        upload = SimpleUploadedFile(
            "purchase-inquiry.pdf",
            buffer.getvalue(),
            content_type="application/pdf",
        )

        text = _extract_text_from_file(upload)

        self.assertIn("Generator quotation", text)
        self.assertEqual(upload.tell(), 0)
        self.assertTrue(_has_extractable_document_text(text))

    def test_unsupported_file_status_is_not_extractable_text(self):
        upload = SimpleUploadedFile(
            "purchase-inquiry.xlsx",
            b"not supported here",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        text = _extract_text_from_file(upload)

        self.assertIn("not supported", text.lower())
        self.assertEqual(upload.tell(), 0)
        self.assertFalse(_has_extractable_document_text(text))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class LoginOtpTests(TestCase):
    def setUp(self):
        mail.outbox = []
        self.user = CustomUser.objects.create_user(
            username="otp-user",
            password="testpass123",
            email="ops@example.com",
            role="FINANCE",
        )

    def _latest_otp(self):
        self.assertEqual(len(mail.outbox), 1)
        match = re.search(r"\b(\d{6})\b", mail.outbox[0].body)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_password_login_sends_otp_without_authenticating(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "otp-user",
                "password": "testpass123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))
        self.assertIn("login_otp", self.client.session)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertIn("Your GMI Terralink sign-in OTP", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].from_email, "otp@gmiterralink.com")
        self.assertEqual(mail.outbox[0].to, ["ops@example.com"])
        self.assertEqual(self.client.session["login_otp"]["email"], "ops@example.com")

    def test_correct_otp_completes_login(self):
        self.client.post(
            reverse("login"),
            {
                "username": "otp-user",
                "password": "testpass123",
                "next": reverse("dashboard"),
            },
        )
        otp_code = self._latest_otp()

        response = self.client.post(
            reverse("login"),
            {
                "otp_code": otp_code,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))
        self.assertEqual(self.client.session.get("_auth_user_id"), str(self.user.pk))
        self.assertNotIn("login_otp", self.client.session)

    def test_account_without_email_still_uses_shared_otp_inbox(self):
        CustomUser.objects.create_user(
            username="no-email",
            password="testpass123",
            role="FINANCE",
        )

        response = self.client.post(
            reverse("login"),
            {
                "username": "no-email",
                "password": "testpass123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))
        self.assertIn("login_otp", self.client.session)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["otp@gmiterralink.com"])

    def test_otp_email_test_uses_current_users_assigned_email(self):
        admin_user = CustomUser.objects.create_user(
            username="otp-admin",
            password="testpass123",
            email="admin-otp@example.com",
            role="ADMIN",
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("user_list"),
            {"action": "test_otp_email"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin-otp@example.com"])
        self.assertIn("assigned OTP delivery address", mail.outbox[0].body)


class LaneSwitchingTests(TestCase):
    def test_procurement_can_switch_to_logistics_and_all_lanes(self):
        user = CustomUser.objects.create_user(
            username="lane-procurement",
            password="testpass123",
            role="PROCUREMENT",
        )
        self.client.force_login(user)

        self.assertTrue(_can_switch_lane(user))

        response = self.client.post(
            reverse("set_lane"),
            {"lane": "logistics", "next": reverse("dashboard")},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get("active_lane"), "logistics")

        self.client.post(
            reverse("set_lane"),
            {"lane": "all", "next": reverse("dashboard")},
        )
        self.assertEqual(self.client.session.get("active_lane"), "all")

    def test_office_admin_has_procurement_capabilities(self):
        user = CustomUser.objects.create_user(
            username="lane-office-admin",
            password="testpass123",
            role="OFFICE_ADMIN",
        )

        self.assertTrue(role_has_procurement_permissions(user))
        self.assertTrue(_can_manage_general_documents(user))


class GeneralDocumentCreateTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

        self.user = CustomUser.objects.create_user(
            username="general-doc-finance",
            password="testpass123",
            role="FINANCE",
        )
        self.client_record = Client.objects.create(
            name="General Document Client",
            contact_person="General Document Client",
            phone="0000000000",
            address="Test address",
            created_by=self.user,
        )
        self.client.force_login(self.user)

    def _document_payload(self, status):
        return {
            "client": str(self.client_record.pk),
            "transaction": "",
            "purpose": "SERVICE",
            "custom_purpose": "",
            "status": status,
            "currency": "USD",
            "tax_amount": "0",
            "discount_amount": "0",
            "notes": "",
            "terms": "",
            "item_description": ["General service"],
            "item_quantity": ["2"],
            "item_unit_price": ["25"],
        }

    def test_general_invoice_create_posts_successfully(self):
        payload = self._document_payload("ISSUED")
        payload["due_date"] = ""

        response = self.client.post(reverse("general_invoice_create"), payload)

        invoice = GeneralInvoice.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url, reverse("general_invoice_detail", kwargs={"pk": invoice.pk})
        )
        self.assertEqual(invoice.subtotal, Decimal("50"))
        self.assertEqual(invoice.created_by, self.user)

    def test_general_quotation_create_posts_successfully(self):
        payload = self._document_payload("SENT")
        payload["valid_until"] = ""

        response = self.client.post(reverse("general_quotation_create"), payload)

        quotation = GeneralQuotation.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("general_quotation_detail", kwargs={"pk": quotation.pk}),
        )
        self.assertEqual(quotation.subtotal, Decimal("50"))
        self.assertEqual(quotation.created_by, self.user)

    def test_general_document_previews_include_branding(self):
        quotation = GeneralQuotation.objects.create(
            client=self.client_record,
            created_by=self.user,
            status="SENT",
            currency="USD",
            subtotal=Decimal("50"),
            items=[
                {
                    "description": "General service",
                    "quantity": "2",
                    "unit_price": "25",
                    "amount": "50",
                }
            ],
        )
        invoice = GeneralInvoice.objects.create(
            client=self.client_record,
            created_by=self.user,
            status="ISSUED",
            currency="USD",
            subtotal=Decimal("50"),
            items=[
                {
                    "description": "General service",
                    "quantity": "2",
                    "unit_price": "25",
                    "amount": "50",
                }
            ],
        )
        payment = GeneralPayment.objects.create(
            invoice=invoice,
            amount=Decimal("10"),
            currency="USD",
            method="CASH",
            created_by=self.user,
        )

        rendered_documents = (
            render_to_string(
                "logistics/pdf/general_quotation_standalone.html",
                {"quotation": quotation},
            ),
            render_to_string(
                "logistics/pdf/general_invoice_standalone.html",
                {"invoice": invoice},
            ),
            render_to_string(
                "logistics/pdf/general_receipt_standalone.html",
                {"receipt": payment.receipt},
            ),
        )

        for rendered in rendered_documents:
            self.assertIn("GMI TERRALINK", rendered)
            self.assertIn("Uganda Branch | Kampala", rendered)

    def test_general_invoice_can_be_signed(self):
        invoice = GeneralInvoice.objects.create(
            client=self.client_record,
            created_by=self.user,
            status="ISSUED",
            currency="USD",
            subtotal=Decimal("50"),
            items=[
                {
                    "description": "General service",
                    "quantity": "2",
                    "unit_price": "25",
                    "amount": "50",
                }
            ],
        )
        SignatureProfile.objects.create(
            user=self.user,
            title="Finance Manager",
            signature_image=SimpleUploadedFile("signature.txt", b"signature"),
        )

        response = self.client.post(
            reverse("general_invoice_sign", kwargs={"pk": invoice.pk}),
            {"note": "Approved"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url, reverse("general_invoice_detail", kwargs={"pk": invoice.pk})
        )
        signature = DocumentSignature.objects.get(
            content_type=ContentType.objects.get_for_model(
                invoice, for_concrete_model=False
            ),
            object_id=invoice.pk,
        )
        self.assertEqual(signature.signer_name, self.user.username)
        self.assertEqual(signature.note, "Approved")


class UserManagementTests(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_superuser(
            username="owner",
            password="testpass123",
            email="owner@example.com",
        )
        self.staff_user = CustomUser.objects.create_user(
            username="staff-user",
            password="testpass123",
            email="wrong@example.com",
            role="FINANCE",
        )

    def test_superuser_can_update_staff_otp_email(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("user_list"),
            {
                "action": "update_email",
                "user_id": self.staff_user.pk,
                "email": "correct@example.com",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("user_list"))
        self.staff_user.refresh_from_db()
        self.assertEqual(self.staff_user.email, "correct@example.com")

    def test_invalid_email_is_rejected(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("user_list"),
            {
                "action": "update_email",
                "user_id": self.staff_user.pk,
                "email": "not-an-email",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.staff_user.refresh_from_db()
        self.assertEqual(self.staff_user.email, "wrong@example.com")


class DocumentArchiveTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

        self.director = CustomUser.objects.create_user(
            username="director",
            password="testpass123",
            role="DIRECTOR",
        )
        self.finance = CustomUser.objects.create_user(
            username="finance",
            password="testpass123",
            role="FINANCE",
        )
        self.procurement = CustomUser.objects.create_user(
            username="procurement-docs",
            password="testpass123",
            role="PROCUREMENT",
        )
        self.customer = Client.objects.create(
            name="Lakeview Grand Hotel",
            contact_person="Amina",
            phone="+256700000000",
            email="amina@example.com",
            address="Kampala",
            created_by=self.director,
        )
        self.transaction = Transaction.objects.create(
            customer=self.customer,
            description="Hotel supplies",
            created_by=self.director,
        )
        self.purchase_order = PurchaseOrder.objects.create(
            transaction=self.transaction,
            supplier_name="Archive Supplier",
            supplier_address="Kampala",
            items=[
                {
                    "description": "Solar battery",
                    "quantity": "2",
                    "unit_price": 100,
                    "amount": 200,
                    "total": 200,
                }
            ],
            subtotal=200,
            created_by=self.procurement,
        )

    def _archive_for(self, user, filename):
        document = Document.objects.create(
            transaction=self.transaction,
            document_type="INQUIRY",
            original_file=SimpleUploadedFile(
                filename, b"department upload", content_type="text/plain"
            ),
            uploaded_by=user,
        )
        return DocumentArchive.create_from_document(document, archived_by=user)

    def test_upload_without_extracted_text_is_still_archived(self):
        self.client.force_login(self.finance)

        with patch("logistics.views._extract_text_from_file", return_value=""):
            response = self.client.post(
                reverse(
                    "transaction_document_upload", kwargs={"pk": self.transaction.pk}
                ),
                {
                    "document_type": "INQUIRY",
                    "original_file": SimpleUploadedFile(
                        "blank-ish.txt", b"no readable text", content_type="text/plain"
                    ),
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Document.objects.count(), 1)
        self.assertEqual(DocumentArchive.objects.count(), 1)
        self.assertEqual(DocumentArchive.objects.get().archived_by, self.finance)

    def test_protected_media_renders_archived_pdf_inline(self):
        archive = self._archive_for(self.finance, "finance-proof.pdf")
        self.client.force_login(self.finance)

        response = self.client.get(
            reverse("protected_media", kwargs={"path": archive.archived_file.name})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("inline", response["Content-Disposition"])
        self.assertIn("finance-proof.pdf", response["Content-Disposition"])

    def test_supplier_payment_proof_is_archived(self):
        payment = SupplierPayment.objects.create(
            purchase_order=self.purchase_order,
            supplier_name="Archive Supplier",
            amount="75.00",
            currency="USD",
            method="BANK",
            reference="SUP-ARCH-1",
            proof_of_payment=SimpleUploadedFile(
                "supplier-proof.txt", b"supplier proof", content_type="text/plain"
            ),
            created_by=self.procurement,
        )

        archive = DocumentArchive.objects.get(source_model="SupplierPayment")
        self.assertEqual(archive.source_object_id, str(payment.pk))
        self.assertEqual(archive.transaction, self.transaction)
        self.assertEqual(archive.archived_by, self.procurement)
        self.assertEqual(archive.original_filename, "supplier-proof.txt")
        self.assertTrue(
            archive.archived_file.name.startswith("transactions/archive/originals/")
        )

    def test_archive_visibility_is_limited_to_department_except_director(self):
        finance_archive = self._archive_for(self.finance, "finance.txt")
        procurement_archive = self._archive_for(self.procurement, "procurement.txt")
        url = reverse("document_archive_list")

        self.client.force_login(self.finance)
        finance_response = self.client.get(url)
        self.assertContains(finance_response, finance_archive.original_filename)
        self.assertNotContains(finance_response, procurement_archive.original_filename)

        self.client.force_login(self.procurement)
        procurement_response = self.client.get(url)
        self.assertContains(procurement_response, procurement_archive.original_filename)
        self.assertNotContains(procurement_response, finance_archive.original_filename)

        self.client.force_login(self.director)
        director_response = self.client.get(url)
        self.assertContains(director_response, finance_archive.original_filename)
        self.assertContains(director_response, procurement_archive.original_filename)


class ProformaFinalInvoiceOneToOneTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="procurement",
            password="testpass123",
            role="ADMIN",
        )
        self.customer = Client.objects.create(
            name="Lakeview Grand Hotel",
            contact_person="Amina",
            phone="+256700000000",
            email="amina@example.com",
            address="Kampala",
            created_by=self.user,
        )
        self.transaction = Transaction.objects.create(
            customer=self.customer,
            description="Hotel supplies",
            created_by=self.user,
        )
        self.proforma = ProformaInvoice.objects.create(
            transaction=self.transaction,
            items=[
                {
                    "description": "Solar battery",
                    "quantity": "2",
                    "sales_price": 100,
                    "total": 200,
                }
            ],
            subtotal=200,
            validity_date="2026-06-18",
            created_by=self.user,
        )

    def test_confirming_same_proforma_twice_reuses_existing_invoice(self):
        self.client.force_login(self.user)
        url = reverse("sourcing_proforma_confirm", kwargs={"pk": self.proforma.pk})

        first_response = self.client.post(url)
        second_response = self.client.post(url)

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        self.assertEqual(FinalInvoice.objects.count(), 1)
        invoice = FinalInvoice.objects.get()
        self.assertEqual(invoice.proforma_id, self.proforma.pk)
        self.assertIn(str(invoice.pk), second_response["Location"])

    def test_confirming_proforma_preserves_line_total_amounts(self):
        self.client.force_login(self.user)
        url = reverse("sourcing_proforma_confirm", kwargs={"pk": self.proforma.pk})

        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        invoice = FinalInvoice.objects.get()
        self.assertEqual(invoice.subtotal, Decimal("200.00"))
        self.assertEqual(invoice.items[0]["amount"], 200.0)
        self.assertEqual(invoice.items[0]["total"], 200.0)
        self.assertEqual(invoice.items[0]["unit_price"], 100.0)


class PurchaseOrderSplitTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="po-admin",
            password="testpass123",
            role="ADMIN",
        )
        self.customer = Client.objects.create(
            name="Lakeview Grand Hotel",
            contact_person="Amina",
            phone="+256700000000",
            email="amina@example.com",
            address="Kampala",
            created_by=self.user,
        )
        self.transaction = Transaction.objects.create(
            customer=self.customer,
            description="Hotel supplies",
            created_by=self.user,
        )
        self.purchase_order = PurchaseOrder.objects.create(
            transaction=self.transaction,
            supplier_name="Supplier Pending",
            supplier_address="",
            items=[
                {
                    "description": "Solar battery",
                    "quantity": "5",
                    "unit_price": 100,
                    "amount": 500,
                    "total": 500,
                }
            ],
            subtotal=500,
            created_by=self.user,
        )
        self.client.force_login(self.user)

    def _split_payload(self, quantity="2"):
        return {
            "line_index": "0",
            "split_quantity": quantity,
            "supplier_name": "Split Supplier",
            "supplier_address": "Kampala",
            "notes": "Supplier allocation",
        }

    def _create_split(self, quantity="2"):
        self.client.post(
            reverse(
                "purchase_order_split_create", kwargs={"pk": self.purchase_order.pk}
            ),
            self._split_payload(quantity),
        )
        return PurchaseOrder.objects.get(parent_po=self.purchase_order)

    def test_purchase_order_pdf_redirects_to_uniform_preview(self):
        preview_url = reverse(
            "purchase_order_html_preview", kwargs={"pk": self.purchase_order.pk}
        )

        response = self.client.get(
            reverse("purchase_order_pdf", kwargs={"pk": self.purchase_order.pk})
        )

        self.assertRedirects(
            response,
            f"{preview_url}?download=1",
            fetch_redirect_response=False,
        )

    def test_purchase_order_preview_uses_uniform_item_columns(self):
        response = self.client.get(
            reverse(
                "purchase_order_html_preview", kwargs={"pk": self.purchase_order.pk}
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unit Cost")
        self.assertContains(response, "Line Total")
        self.assertContains(response, "Solar battery")
        self.assertContains(response, "USD 100.00")
        self.assertContains(response, "USD 500.00")

    def test_purchase_order_detail_embeds_uniform_preview(self):
        response = self.client.get(
            reverse("purchase_order_detail", kwargs={"pk": self.purchase_order.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="purchase-order-preview-frame"')
        self.assertContains(
            response,
            reverse(
                "purchase_order_html_preview", kwargs={"pk": self.purchase_order.pk}
            ),
        )
        self.assertContains(response, "Print Preview")
        self.assertContains(response, "Download PDF")

    def test_parent_po_detail_exposes_split_document_actions(self):
        split_po = self._create_split("2")

        response = self.client.get(
            reverse("purchase_order_detail", kwargs={"pk": self.purchase_order.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, split_po.po_number)
        self.assertContains(
            response, reverse("purchase_order_detail", kwargs={"pk": split_po.pk})
        )
        self.assertContains(
            response,
            f"{reverse('purchase_order_html_preview', kwargs={'pk': split_po.pk})}?download=1",
        )
        self.assertContains(
            response,
            f"{reverse('purchase_order_pdf', kwargs={'pk': split_po.pk})}?download=1",
        )

    def test_finance_can_access_purchase_orders(self):
        finance_user = CustomUser.objects.create_user(
            username="po-finance",
            password="testpass123",
            role="FINANCE",
        )
        self.client.force_login(finance_user)

        list_response = self.client.get(reverse("purchase_order_list"))
        detail_response = self.client.get(
            reverse("purchase_order_detail", kwargs={"pk": self.purchase_order.pk})
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Purchase Orders")
        self.assertContains(detail_response, reverse("purchase_order_list"))
        self.assertContains(detail_response, "Edit PO")

    def test_split_creation_deducts_quantity_from_main_po_line(self):
        response = self.client.post(
            reverse(
                "purchase_order_split_create", kwargs={"pk": self.purchase_order.pk}
            ),
            self._split_payload("2"),
        )

        self.assertEqual(response.status_code, 302)
        split_po = PurchaseOrder.objects.get(parent_po=self.purchase_order)
        self.purchase_order.refresh_from_db()
        self.assertEqual(split_po.original_po_line_index, 0)
        self.assertEqual(split_po.po_number, f"{self.purchase_order.po_number}-SP1")
        self.assertEqual(split_po.original_po_line_quantity, Decimal("5.00"))
        self.assertEqual(split_po.split_quantity, Decimal("2.00"))
        self.assertEqual(split_po.split_mode, "QUANTITY")
        self.assertEqual(split_po.split_lines[0]["description"], "Solar battery")
        self.assertEqual(self.purchase_order.items[0]["quantity"], "3")
        self.assertEqual(split_po.items[0]["quantity"], "2")
        self.assertEqual(self.purchase_order.subtotal, Decimal("300.00"))
        self.assertEqual(split_po.subtotal, Decimal("200.00"))

    def test_base_and_split_pos_are_paid_individually_with_shared_deposit_cap(self):
        split_po = self._create_split("2")
        finance_user = CustomUser.objects.create_user(
            username="po-finance",
            password="testpass123",
            role="FINANCE",
        )
        self.client.force_login(finance_user)
        TransactionPaymentRecord.objects.create(
            transaction=self.transaction,
            amount_due_snapshot=Decimal("500.00"),
            amount=Decimal("350.00"),
            currency="USD",
            payment_method="bank_transfer",
            reference="CLIENT-DEP-1",
            created_by=finance_user,
        )

        base_payment_response = self.client.post(
            reverse(
                "record_supplier_payment", kwargs={"po_pk": self.purchase_order.pk}
            ),
            {
                "supplier_name": "Main Supplier",
                "amount": "250.00",
                "currency": "USD",
                "method": "BANK",
                "reference": "SUP-BASE-1",
                "paid_at": "2026-05-22T10:00",
                "notes": "Base PO supplier portion",
            },
        )
        over_cap_response = self.client.post(
            reverse("record_supplier_payment", kwargs={"po_pk": split_po.pk}),
            {
                "supplier_name": "Split Supplier",
                "amount": "150.00",
                "currency": "USD",
                "method": "BANK",
                "reference": "SUP-SPLIT-1",
                "paid_at": "2026-05-22T10:05",
                "notes": "Split PO supplier portion",
            },
        )

        self.assertEqual(base_payment_response.status_code, 302)
        self.assertEqual(over_cap_response.status_code, 200)
        self.assertEqual(SupplierPayment.objects.count(), 1)
        payment = SupplierPayment.objects.get()
        self.assertEqual(payment.purchase_order_id, self.purchase_order.pk)
        self.assertContains(
            over_cap_response, "exceeds the allowed client deposit room"
        )

    def test_invoice_payment_snapshot_allocates_goods_shipping_then_company_fees(self):
        invoice = FinalInvoice.objects.create(
            transaction=self.transaction,
            items=[],
            subtotal=Decimal("2112.00"),
            sourcing_fee=Decimal("400.00"),
            shipping_cost=Decimal("300.00"),
            service_fee=Decimal("180.00"),
            created_by=self.user,
        )

        partial_snapshot = _final_invoice_payment_snapshot(invoice, Decimal("1000.00"))
        shipping_snapshot = _final_invoice_payment_snapshot(invoice, Decimal("2500.00"))

        self.assertEqual(partial_snapshot["item_balance"], Decimal("1112.00"))
        self.assertEqual(partial_snapshot["shipping_balance"], Decimal("300.00"))
        self.assertEqual(partial_snapshot["company_fee_balance"], Decimal("580.00"))
        self.assertEqual(shipping_snapshot["item_balance"], Decimal("0.00"))
        self.assertEqual(shipping_snapshot["shipping_balance"], Decimal("0.00"))
        self.assertEqual(shipping_snapshot["company_fee_paid"], Decimal("88.00"))
        self.assertEqual(shipping_snapshot["company_fee_balance"], Decimal("492.00"))

    def test_quantity_splits_use_sequence_numbers_and_supplier_cost(self):
        first_response = self.client.post(
            reverse(
                "purchase_order_split_create", kwargs={"pk": self.purchase_order.pk}
            ),
            {
                **self._split_payload("2"),
                "split_unit_price": "90",
            },
        )
        second_response = self.client.post(
            reverse(
                "purchase_order_split_create", kwargs={"pk": self.purchase_order.pk}
            ),
            {
                **self._split_payload("1"),
                "split_unit_price": "80",
            },
        )

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        splits = list(
            PurchaseOrder.objects.filter(parent_po=self.purchase_order).order_by(
                "created_at"
            )
        )
        self.assertEqual(splits[0].po_number, f"{self.purchase_order.po_number}-SP1")
        self.assertEqual(splits[1].po_number, f"{self.purchase_order.po_number}-SP2")
        self.assertEqual(
            Decimal(str(splits[0].items[0]["unit_price"])), Decimal("90.0")
        )
        self.assertEqual(
            Decimal(str(splits[1].items[0]["unit_price"])), Decimal("80.0")
        )
        self.assertEqual(splits[0].subtotal, Decimal("180.00"))
        self.assertEqual(splits[1].subtotal, Decimal("80.00"))

    def test_whole_item_split_moves_selected_lines_from_main_po(self):
        self.purchase_order.items = [
            {
                "description": "Solar battery",
                "quantity": "5",
                "unit_price": 100,
                "amount": 500,
                "total": 500,
            },
            {
                "description": "Inverter",
                "quantity": "1",
                "unit_price": 300,
                "amount": 300,
                "total": 300,
            },
        ]
        self.purchase_order.subtotal = 800
        self.purchase_order.save(update_fields=["items", "subtotal", "updated_at"])

        response = self.client.post(
            reverse(
                "purchase_order_split_create", kwargs={"pk": self.purchase_order.pk}
            ),
            {
                "split_mode": "ITEMS",
                "selected_line_indices": ["1"],
                "supplier_name": "Inverter Supplier",
                "supplier_address": "Kampala",
            },
        )

        self.assertEqual(response.status_code, 302)
        split_po = PurchaseOrder.objects.get(parent_po=self.purchase_order)
        self.purchase_order.refresh_from_db()
        self.assertEqual(split_po.split_mode, "ITEMS")
        self.assertEqual(split_po.items[0]["description"], "Inverter")
        self.assertEqual(split_po.items[0]["quantity"], "1")
        self.assertEqual(split_po.split_lines[0]["description"], "Inverter")
        self.assertEqual(len(self.purchase_order.items), 1)
        self.assertEqual(self.purchase_order.items[0]["description"], "Solar battery")
        self.assertEqual(self.purchase_order.subtotal, Decimal("500.00"))
        self.assertEqual(split_po.subtotal, Decimal("300.00"))

    def test_whole_item_split_cannot_move_every_main_po_line(self):
        self.purchase_order.items = [
            {
                "description": "Solar battery",
                "quantity": "5",
                "unit_price": 100,
                "amount": 500,
                "total": 500,
            },
            {
                "description": "Inverter",
                "quantity": "1",
                "unit_price": 300,
                "amount": 300,
                "total": 300,
            },
        ]
        self.purchase_order.subtotal = 800
        self.purchase_order.save(update_fields=["items", "subtotal", "updated_at"])

        response = self.client.post(
            reverse(
                "purchase_order_split_create", kwargs={"pk": self.purchase_order.pk}
            ),
            {
                "split_mode": "ITEMS",
                "selected_line_indices": ["0", "1"],
                "supplier_name": "All Items Supplier",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            PurchaseOrder.objects.filter(parent_po=self.purchase_order).exists()
        )
        self.purchase_order.refresh_from_db()
        self.assertEqual(len(self.purchase_order.items), 2)

    def test_split_requires_original_quantity_greater_than_two(self):
        self.purchase_order.items = [
            {
                "description": "Small batch",
                "quantity": "2",
                "unit_price": 50,
                "amount": 100,
                "total": 100,
            }
        ]
        self.purchase_order.subtotal = 100
        self.purchase_order.save(update_fields=["items", "subtotal", "updated_at"])

        response = self.client.post(
            reverse(
                "purchase_order_split_create", kwargs={"pk": self.purchase_order.pk}
            ),
            self._split_payload("1"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            PurchaseOrder.objects.filter(parent_po=self.purchase_order).exists()
        )

    def test_split_quantity_cannot_consume_entire_po_line(self):
        response = self.client.post(
            reverse(
                "purchase_order_split_create", kwargs={"pk": self.purchase_order.pk}
            ),
            self._split_payload("5"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            PurchaseOrder.objects.filter(parent_po=self.purchase_order).exists()
        )
        self.purchase_order.refresh_from_db()
        self.assertEqual(self.purchase_order.items[0]["quantity"], "5")

    def test_split_quantity_update_recalculates_main_po_balance(self):
        split_po = self._create_split("2")

        response = self.client.post(
            reverse("purchase_order_split_quantity_update", kwargs={"pk": split_po.pk}),
            {"split_quantity": "3"},
        )

        self.assertEqual(response.status_code, 302)
        split_po.refresh_from_db()
        self.purchase_order.refresh_from_db()
        self.assertEqual(split_po.split_quantity, Decimal("3.00"))
        self.assertEqual(split_po.items[0]["quantity"], "3")
        self.assertEqual(self.purchase_order.items[0]["quantity"], "2")

    def test_split_quantity_update_cannot_zero_main_po_balance(self):
        split_po = self._create_split("2")

        response = self.client.post(
            reverse("purchase_order_split_quantity_update", kwargs={"pk": split_po.pk}),
            {"split_quantity": "5"},
        )

        self.assertEqual(response.status_code, 200)
        split_po.refresh_from_db()
        self.purchase_order.refresh_from_db()
        self.assertEqual(split_po.split_quantity, Decimal("2.00"))
        self.assertEqual(self.purchase_order.items[0]["quantity"], "3")

    def test_received_purchase_order_blocks_splits_and_split_quantity_edits(self):
        self.purchase_order.status = "RECEIVED"
        self.purchase_order.save(update_fields=["status", "updated_at"])

        response = self.client.post(
            reverse(
                "purchase_order_split_create", kwargs={"pk": self.purchase_order.pk}
            ),
            self._split_payload("2"),
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            PurchaseOrder.objects.filter(parent_po=self.purchase_order).exists()
        )

        self.purchase_order.status = "PENDING"
        self.purchase_order.save(update_fields=["status", "updated_at"])
        split_po = self._create_split("2")
        split_po.status = "RECEIVED"
        split_po.save(update_fields=["status", "updated_at"])

        response = self.client.post(
            reverse("purchase_order_split_quantity_update", kwargs={"pk": split_po.pk}),
            {"split_quantity": "3"},
        )

        self.assertEqual(response.status_code, 302)
        split_po.refresh_from_db()
        self.assertEqual(split_po.split_quantity, Decimal("2.00"))

    def test_procurement_can_edit_po_and_control_splits(self):
        procurement_user = CustomUser.objects.create_user(
            username="po-procurement",
            password="testpass123",
            role="PROCUREMENT",
        )
        self.client.force_login(procurement_user)

        detail_response = self.client.get(
            reverse("purchase_order_detail", kwargs={"pk": self.purchase_order.pk})
        )

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Purchase Orders")
        self.assertContains(detail_response, "Split PO")
        self.assertContains(detail_response, "Edit PO")

        edit_response = self.client.post(
            reverse("purchase_order_update", kwargs={"pk": self.purchase_order.pk}),
            {
                "supplier_name": "Edited Supplier",
                "status": "SENT",
                "item_desc[]": ["Changed item"],
                "item_qty[]": ["5"],
                "item_unit_price[]": ["100"],
            },
        )

        self.assertEqual(edit_response.status_code, 302)
        self.purchase_order.refresh_from_db()
        self.assertEqual(self.purchase_order.supplier_name, "Edited Supplier")
        self.assertEqual(self.purchase_order.items[0]["description"], "Changed Item")

        split_response = self.client.post(
            reverse(
                "purchase_order_split_create", kwargs={"pk": self.purchase_order.pk}
            ),
            self._split_payload("2"),
        )

        self.assertEqual(split_response.status_code, 302)
        self.assertTrue(
            PurchaseOrder.objects.filter(parent_po=self.purchase_order).exists()
        )

    def test_unpaid_purchase_order_cannot_be_marked_fulfilled(self):
        response = self.client.post(
            reverse("purchase_order_update", kwargs={"pk": self.purchase_order.pk}),
            {
                "supplier_name": "Supplier Pending",
                "status": "FULFILLED",
                "item_desc[]": ["Solar battery"],
                "item_qty[]": ["5"],
                "item_unit_price[]": ["100"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cannot be marked received or fulfilled")
        self.purchase_order.refresh_from_db()
        self.assertEqual(self.purchase_order.status, "PENDING")

    def test_manual_received_status_without_supplier_payment_does_not_clear_po(self):
        self.purchase_order.status = "RECEIVED"
        self.purchase_order.save(update_fields=["status", "updated_at"])

        response = self.client.get(
            reverse("purchase_order_detail", kwargs={"pk": self.purchase_order.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "served/fulfilled")
        self.assertContains(response, "Unpaid")


class ClientCleanupTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

        self.admin = CustomUser.objects.create_user(
            username="cleanup-admin",
            password="testpass123",
            role="ADMIN",
        )
        self.customer = Client.objects.create(
            name="Derrick Trading",
            contact_person="Derrick",
            phone="0700000000",
            email="derrick@example.com",
            address="Kampala",
            created_by=self.admin,
        )
        self.other_customer = Client.objects.create(
            name="Other Client",
            contact_person="Amina",
            phone="0711111111",
            email="amina@example.com",
            address="Entebbe",
            created_by=self.admin,
        )
        self.transaction = Transaction.objects.create(
            customer=self.customer,
            description="Cleanup goods",
            created_by=self.admin,
        )
        self.other_transaction = Transaction.objects.create(
            customer=self.other_customer,
            description="Separate goods",
            created_by=self.admin,
        )
        self.document = self._create_document(self.transaction, "derrick-pi.txt")
        self.other_document = self._create_document(
            self.other_transaction, "other-pi.txt"
        )
        self.client.force_login(self.admin)

    def _create_document(self, transaction, filename):
        document = Document.objects.create(
            transaction=transaction,
            document_type="CLIENT_PI",
            original_file=SimpleUploadedFile(
                filename, b"client purchase inquiry", content_type="text/plain"
            ),
            uploaded_by=self.admin,
        )
        DocumentArchive.create_from_document(document, archived_by=self.admin)
        return document

    def test_bulk_document_delete_only_removes_selected_client_documents(self):
        response = self.client.post(
            reverse("client_documents_bulk_delete", kwargs={"pk": self.customer.pk}),
            {"document_ids": [str(self.document.pk), str(self.other_document.pk)]},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Document.objects.filter(pk=self.document.pk).exists())
        self.assertFalse(
            DocumentArchive.objects.filter(
                source_model="Document", source_object_id=str(self.document.pk)
            ).exists()
        )
        self.assertTrue(Document.objects.filter(pk=self.other_document.pk).exists())
        self.assertTrue(
            DocumentArchive.objects.filter(
                source_model="Document", source_object_id=str(self.other_document.pk)
            ).exists()
        )

    def test_client_detail_lists_transaction_documents_inline(self):
        sourcing = Sourcing.objects.create(
            transaction=self.transaction,
            supplier_name="Guangzhou Source Co",
            item_details=[{"description": "Cleanup item", "quantity": "1"}],
            unit_prices={"Cleanup item": "100"},
            notes="Supplier quote ready",
            created_by=self.admin,
        )
        proforma = ProformaInvoice.objects.create(
            transaction=self.transaction,
            source_sourcing=sourcing,
            items=[{"description": "Cleanup item", "quantity": "1", "total": 100}],
            subtotal=Decimal("100.00"),
            validity_date="2026-06-18",
            supplier_name="Guangzhou Source Co",
            created_by=self.admin,
        )
        final_invoice = FinalInvoice.objects.create(
            transaction=self.transaction,
            proforma=proforma,
            items=[{"description": "Cleanup item", "quantity": "1", "total": 100}],
            subtotal=Decimal("100.00"),
            total_amount=Decimal("100.00"),
            created_by=self.admin,
        )
        purchase_order = PurchaseOrder.objects.create(
            transaction=self.transaction,
            proforma=proforma,
            final_invoice=final_invoice,
            supplier_name="Guangzhou Source Co",
            items=[{"description": "Cleanup item", "quantity": "1", "total": 100}],
            subtotal=Decimal("100.00"),
            created_by=self.admin,
        )
        SupplierPayment.objects.create(
            purchase_order=purchase_order,
            supplier_name="Guangzhou Source Co",
            amount=Decimal("50.00"),
            currency="USD",
            method="BANK",
            reference="SUP-CLEAN-1",
            created_by=self.admin,
        )
        TransactionPaymentRecord.objects.create(
            transaction=self.transaction,
            final_invoice=final_invoice,
            amount_due_snapshot=Decimal("100.00"),
            amount=Decimal("60.00"),
            currency="USD",
            payment_method="bank_transfer",
            reference="CLIENT-CLEAN-1",
            created_by=self.admin,
        )

        response = self.client.get(
            reverse("client_detail", kwargs={"pk": self.customer.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.transaction.transaction_id)
        self.assertContains(response, "Cleanup goods")
        self.assertContains(response, "Sourcing trade")
        self.assertContains(response, "Guangzhou Source Co")
        self.assertContains(response, "Supplier quote ready")
        self.assertContains(response, "Proforma")
        self.assertContains(response, "Final invoice")
        self.assertContains(response, purchase_order.po_number)
        self.assertContains(response, "Supplier payment")
        self.assertContains(response, "Client payment")
        self.assertContains(response, "CLIENT-CLEAN-1")
        self.assertContains(response, "Documents to delete or edit")
        self.assertContains(response, "Uploaded document")
        self.assertContains(response, "Client payment receipt")
        self.assertContains(response, "Supplier payment receipt")
        self.assertContains(response, "derrick-pi")
        self.assertContains(
            response, reverse("sourcing_update", kwargs={"pk": sourcing.pk})
        )
        self.assertContains(
            response, reverse("sourcing_proforma_update", kwargs={"pk": proforma.pk})
        )
        self.assertContains(
            response,
            reverse("sourcing_final_invoice_update", kwargs={"pk": final_invoice.pk}),
        )
        self.assertContains(
            response,
            reverse("purchase_order_update", kwargs={"pk": purchase_order.pk}),
        )
        self.assertContains(
            response, reverse("transaction_update", kwargs={"pk": self.transaction.pk})
        )
        self.assertContains(
            response, reverse("document_update", kwargs={"pk": self.document.pk})
        )
        self.assertContains(
            response,
            reverse(
                "client_cleanup_record_delete",
                kwargs={
                    "pk": self.customer.pk,
                    "record_type": "final_invoice",
                    "record_pk": final_invoice.pk,
                },
            ),
        )
        self.assertContains(response, "Delete")
        self.assertNotContains(response, 'name="document_ids"')
        self.assertNotContains(response, "other-pi")

    def test_client_cleanup_record_delete_removes_final_invoice_dependencies(self):
        proforma = ProformaInvoice.objects.create(
            transaction=self.transaction,
            items=[{"description": "Cleanup item", "quantity": "1", "total": 100}],
            subtotal=Decimal("100.00"),
            validity_date="2026-06-18",
            created_by=self.admin,
        )
        final_invoice = FinalInvoice.objects.create(
            transaction=self.transaction,
            proforma=proforma,
            items=[{"description": "Cleanup item", "quantity": "1", "total": 100}],
            subtotal=Decimal("100.00"),
            total_amount=Decimal("100.00"),
            created_by=self.admin,
        )
        purchase_order = PurchaseOrder.objects.create(
            transaction=self.transaction,
            proforma=proforma,
            final_invoice=final_invoice,
            supplier_name="Cleanup Supplier",
            items=[{"description": "Cleanup item", "quantity": "1", "total": 100}],
            subtotal=Decimal("100.00"),
            created_by=self.admin,
        )
        supplier_payment = SupplierPayment.objects.create(
            purchase_order=purchase_order,
            supplier_name="Cleanup Supplier",
            amount=Decimal("50.00"),
            currency="USD",
            method="BANK",
            reference="SUP-CLEAN-DELETE",
            created_by=self.admin,
        )
        client_payment = TransactionPaymentRecord.objects.create(
            transaction=self.transaction,
            final_invoice=final_invoice,
            amount_due_snapshot=Decimal("100.00"),
            amount=Decimal("60.00"),
            currency="USD",
            payment_method="bank_transfer",
            reference="CLIENT-CLEAN-DELETE",
            created_by=self.admin,
        )
        receipt_pk = client_payment.receipt.pk

        response = self.client.post(
            reverse(
                "client_cleanup_record_delete",
                kwargs={
                    "pk": self.customer.pk,
                    "record_type": "final_invoice",
                    "record_pk": final_invoice.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(FinalInvoice.objects.filter(pk=final_invoice.pk).exists())
        self.assertFalse(PurchaseOrder.objects.filter(pk=purchase_order.pk).exists())
        self.assertFalse(
            SupplierPayment.objects.filter(pk=supplier_payment.pk).exists()
        )
        self.assertFalse(
            TransactionPaymentRecord.objects.filter(pk=client_payment.pk).exists()
        )
        self.assertFalse(Receipt.objects.filter(pk=receipt_pk).exists())
        self.assertTrue(ProformaInvoice.objects.filter(pk=proforma.pk).exists())

    def test_client_delete_get_renders_confirmation_without_deleting(self):
        response = self.client.get(
            reverse("client_delete", kwargs={"pk": self.customer.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Client.objects.filter(pk=self.customer.pk).exists())

    def test_office_admin_cannot_delete_client_data(self):
        office_admin = CustomUser.objects.create_user(
            username="cleanup-office-admin",
            password="testpass123",
            role="OFFICE_ADMIN",
        )
        self.client.force_login(office_admin)

        document_response = self.client.post(
            reverse("client_documents_bulk_delete", kwargs={"pk": self.customer.pk}),
            {"document_ids": [str(self.document.pk)]},
        )
        client_response = self.client.post(
            reverse("client_delete", kwargs={"pk": self.customer.pk}),
            {"confirm_name": self.customer.name},
        )

        self.assertEqual(document_response.status_code, 302)
        self.assertEqual(client_response.status_code, 302)
        self.assertTrue(Client.objects.filter(pk=self.customer.pk).exists())
        self.assertTrue(Document.objects.filter(pk=self.document.pk).exists())

    def test_client_delete_removes_protected_related_records(self):
        loading = Loading.objects.create(
            loading_id="LOAD-CLEAN-1",
            client=self.customer,
            loading_date=timezone.now(),
            item_description="Cleanup cargo",
            origin="Guangzhou",
            destination="Kampala",
            created_by=self.admin,
        )
        self.transaction.source_loading = loading
        self.transaction.save(update_fields=["source_loading"])
        proforma = ProformaInvoice.objects.create(
            transaction=self.transaction,
            loading=loading,
            items=[{"description": "Cleanup item", "quantity": "1", "total": 100}],
            subtotal=Decimal("100.00"),
            validity_date="2026-06-18",
            created_by=self.admin,
        )
        final_invoice = FinalInvoice.objects.create(
            transaction=self.transaction,
            loading=loading,
            proforma=proforma,
            items=[{"description": "Cleanup item", "quantity": "1", "total": 100}],
            subtotal=Decimal("100.00"),
            total_amount=Decimal("100.00"),
            created_by=self.admin,
        )
        PurchaseOrder.objects.create(
            transaction=self.transaction,
            proforma=proforma,
            final_invoice=final_invoice,
            supplier_name="Cleanup Supplier",
            items=[{"description": "Cleanup item", "quantity": "1", "total": 100}],
            subtotal=Decimal("100.00"),
            created_by=self.admin,
        )
        ContainerReturn.objects.create(
            container_number="CLEAN1234567",
            loading=loading,
            return_date=timezone.now(),
            condition="good",
            created_by=self.admin,
        )
        Commission.objects.create(
            client=self.customer,
            amount=Decimal("25.00"),
            currency="USD",
            created_by=self.admin,
        )
        general_quotation = GeneralQuotation.objects.create(
            client=self.customer,
            purpose="SERVICE",
            items=[{"description": "Cleanup service", "quantity": "1", "total": 100}],
            subtotal=Decimal("100.00"),
            created_by=self.admin,
        )
        general_invoice = GeneralInvoice.objects.create(
            client=self.customer,
            quotation=general_quotation,
            purpose="SERVICE",
            items=[{"description": "Cleanup service", "quantity": "1", "total": 100}],
            subtotal=Decimal("100.00"),
            created_by=self.admin,
        )
        general_payment = GeneralPayment.objects.create(
            invoice=general_invoice,
            amount=Decimal("40.00"),
            currency="USD",
            method="BANK_TRANSFER",
            reference="GEN-CLEAN-1",
            created_by=self.admin,
        )
        general_receipt_pk = general_payment.receipt.pk

        response = self.client.post(
            reverse("client_delete", kwargs={"pk": self.customer.pk}),
            {"confirm_name": self.customer.name},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Client.objects.filter(pk=self.customer.pk).exists())
        self.assertFalse(Transaction.objects.filter(pk=self.transaction.pk).exists())
        self.assertFalse(Loading.objects.filter(pk=loading.pk).exists())
        self.assertFalse(Document.objects.filter(pk=self.document.pk).exists())
        self.assertFalse(ProformaInvoice.objects.filter(pk=proforma.pk).exists())
        self.assertFalse(FinalInvoice.objects.filter(pk=final_invoice.pk).exists())
        self.assertFalse(
            GeneralQuotation.objects.filter(pk=general_quotation.pk).exists()
        )
        self.assertFalse(GeneralInvoice.objects.filter(pk=general_invoice.pk).exists())
        self.assertFalse(GeneralPayment.objects.filter(pk=general_payment.pk).exists())
        self.assertFalse(GeneralReceipt.objects.filter(pk=general_receipt_pk).exists())
        self.assertFalse(ContainerReturn.objects.filter(loading=loading).exists())
        self.assertFalse(Commission.objects.filter(client_id=self.customer.pk).exists())
        self.assertTrue(Client.objects.filter(pk=self.other_customer.pk).exists())
