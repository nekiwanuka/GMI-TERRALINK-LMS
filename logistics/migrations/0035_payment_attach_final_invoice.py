from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0034_clear_manual_payment_billing_rate"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="final_invoice",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="logistics_payments",
                to="logistics.finalinvoice",
            ),
        ),
    ]
