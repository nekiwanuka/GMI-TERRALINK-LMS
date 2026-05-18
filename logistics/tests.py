from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from reportlab.pdfgen import canvas

from logistics.models import (
    Client,
    CustomUser,
    FinalInvoice,
    ProformaInvoice,
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
