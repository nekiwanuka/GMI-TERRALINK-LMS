from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0047_finalinvoice_proforma"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorder",
            name="original_po_line_index",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="purchaseorder",
            name="original_po_line_quantity",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True
            ),
        ),
        migrations.AddField(
            model_name="purchaseorder",
            name="original_po_line_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="purchaseorder",
            name="split_quantity",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True
            ),
        ),
        migrations.AlterField(
            model_name="purchaseorder",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("SENT", "Sent to Supplier"),
                    ("RECEIVED", "Received"),
                    ("FULFILLED", "Fulfilled"),
                ],
                default="PENDING",
                max_length=12,
            ),
        ),
    ]
