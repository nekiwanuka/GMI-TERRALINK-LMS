from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from reportlab.pdfgen import canvas

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
