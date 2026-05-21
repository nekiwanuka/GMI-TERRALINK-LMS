from io import BytesIO
from decimal import Decimal
import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from reportlab.pdfgen import canvas

from logistics.models import (
    Client,
    CustomUser,
    Document,
    DocumentArchive,
    FinalInvoice,
    PurchaseOrder,
    ProformaInvoice,
    SupplierPayment,
    Transaction,
)
from logistics.views import _extract_text_from_file, _has_extractable_document_text


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
        self.assertTrue(archive.archived_file.name.startswith("transactions/archive/originals/"))

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
        self.assertEqual(split_po.original_po_line_quantity, Decimal("5.00"))
        self.assertEqual(split_po.split_quantity, Decimal("2.00"))
        self.assertEqual(split_po.split_mode, "QUANTITY")
        self.assertEqual(split_po.split_lines[0]["description"], "Solar battery")
        self.assertEqual(self.purchase_order.items[0]["quantity"], "3")
        self.assertEqual(split_po.items[0]["quantity"], "2")
        self.assertEqual(self.purchase_order.subtotal, Decimal("300.00"))
        self.assertEqual(split_po.subtotal, Decimal("200.00"))

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

    def test_procurement_can_control_po_splits_but_not_directly_edit_po(self):
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
        self.assertNotContains(detail_response, "Edit PO")

        edit_response = self.client.post(
            reverse("purchase_order_update", kwargs={"pk": self.purchase_order.pk}),
            {
                "supplier_name": "Edited Supplier",
                "status": "SENT",
                "item_desc[]": ["Changed item"],
                "item_qty[]": ["1"],
                "item_unit_price[]": ["1"],
            },
        )

        self.assertEqual(edit_response.status_code, 302)
        self.purchase_order.refresh_from_db()
        self.assertEqual(self.purchase_order.supplier_name, "Supplier Pending")
        self.assertEqual(self.purchase_order.items[0]["description"], "Solar battery")

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
