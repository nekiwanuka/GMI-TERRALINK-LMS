from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0023_notification"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentArchive",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "document_type",
                    models.CharField(
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
                ("original_filename", models.CharField(max_length=255)),
                (
                    "archived_file",
                    models.FileField(upload_to="transactions/archive/originals/"),
                ),
                ("extracted_text", models.TextField(blank=True)),
                ("structured_data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "archived_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="archived_documents",
                        to="logistics.customuser",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="archives",
                        to="logistics.document",
                    ),
                ),
                (
                    "transaction",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_archives",
                        to="logistics.transaction",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
