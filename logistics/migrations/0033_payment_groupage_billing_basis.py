from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0032_loading_groupage_measurements"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="billing_basis",
            field=models.CharField(
                choices=[
                    ("manual", "Manual Amount"),
                    ("kg", "Weight (KG)"),
                    ("cbm", "CBM"),
                ],
                default="manual",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="billing_rate",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True
            ),
        ),
    ]
