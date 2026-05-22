from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0048_purchaseorder_split_tracking"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorder",
            name="split_lines",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="purchaseorder",
            name="split_mode",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Not Split"),
                    ("ITEMS", "Whole Items"),
                    ("QUANTITY", "Line Quantity"),
                ],
                default="",
                max_length=12,
            ),
        ),
    ]
