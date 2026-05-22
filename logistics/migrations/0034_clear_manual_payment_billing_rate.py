from django.db import migrations


def clear_manual_payment_rates(apps, schema_editor):
    Payment = apps.get_model("logistics", "Payment")
    Payment.objects.filter(billing_basis="manual").update(billing_rate=None)


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0033_payment_groupage_billing_basis"),
    ]

    operations = [
        migrations.RunPython(clear_manual_payment_rates, migrations.RunPython.noop),
    ]
