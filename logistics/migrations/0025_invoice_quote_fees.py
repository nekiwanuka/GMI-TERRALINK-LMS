from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0024_documentarchive"),
    ]

    operations = [
        migrations.AddField(
            model_name="proformainvoice",
            name="handling_fee",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0.00"), max_digits=14
            ),
        ),
        migrations.AddField(
            model_name="proformainvoice",
            name="shipping_fee",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0.00"), max_digits=14
            ),
        ),
        migrations.AddField(
            model_name="proformainvoice",
            name="sourcing_fee",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0.00"), max_digits=14
            ),
        ),
        migrations.AddField(
            model_name="finalinvoice",
            name="sourcing_fee",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0.00"), max_digits=14
            ),
        ),
    ]
