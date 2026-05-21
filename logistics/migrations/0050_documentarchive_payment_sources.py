from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0049_purchaseorder_split_mode_lines"),
    ]

    operations = [
        migrations.AlterField(
            model_name="documentarchive",
            name="document",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="archives",
                to="logistics.document",
            ),
        ),
        migrations.AlterField(
            model_name="documentarchive",
            name="transaction",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="document_archives",
                to="logistics.transaction",
            ),
        ),
        migrations.AddField(
            model_name="documentarchive",
            name="source_label",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="documentarchive",
            name="source_model",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="documentarchive",
            name="source_object_id",
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
