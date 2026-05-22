from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0043_documentsignature_signer_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="proformainvoice",
            name="source_sourcing",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="generated_proforma",
                to="logistics.sourcing",
            ),
        ),
    ]
