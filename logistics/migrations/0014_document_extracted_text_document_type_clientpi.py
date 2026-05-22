"""
Migration: Add extracted_text field to Document and add CLIENT_PI to document_type choices.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0013_transaction_description_transaction_notes_and_more"),
    ]

    operations = [
        # Add extracted_text field
        migrations.AddField(
            model_name="document",
            name="extracted_text",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Auto-extracted text content from the uploaded document.",
            ),
            preserve_default=False,
        ),
        # Update the document_type field to include CLIENT_PI and set its default
        migrations.AlterField(
            model_name="document",
            name="document_type",
            field=models.CharField(
                choices=[
                    ("CLIENT_PI", "Client Purchase Inquiry (PI)"),
                    ("INQUIRY", "Inquiry"),
                    ("CLEANED", "Cleaned"),
                    ("INVOICE", "Invoice"),
                    ("RECEIPT", "Receipt"),
                ],
                default="CLIENT_PI",
                max_length=20,
            ),
        ),
        # Update help_text on original_file (no schema change, just metadata)
        migrations.AlterField(
            model_name="document",
            name="original_file",
            field=models.FileField(
                help_text="Accepted: PDF, Word (.docx), or plain text files.",
                upload_to="transactions/originals/",
            ),
        ),
    ]
