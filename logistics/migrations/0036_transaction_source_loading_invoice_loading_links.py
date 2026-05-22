from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("logistics", "0035_payment_attach_final_invoice"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaction",
            name="source_loading",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="source_transaction",
                to="logistics.loading",
            ),
        ),
        migrations.AddField(
            model_name="proformainvoice",
            name="loading",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="proforma_invoices",
                to="logistics.loading",
            ),
        ),
        migrations.AddField(
            model_name="finalinvoice",
            name="loading",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="final_invoices",
                to="logistics.loading",
            ),
        ),
    ]
