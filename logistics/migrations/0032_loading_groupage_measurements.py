from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0031_billingcharge_billinginvoice_cargoitemworkflow_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="loading",
            name="cbm",
            field=models.DecimalField(
                blank=True, decimal_places=3, max_digits=10, null=True
            ),
        ),
        migrations.AddField(
            model_name="loading",
            name="packages",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
