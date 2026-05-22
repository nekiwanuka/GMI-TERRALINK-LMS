from django.db import migrations, models


def populate_signer_role(apps, schema_editor):
    DocumentSignature = apps.get_model("logistics", "DocumentSignature")
    for signature in DocumentSignature.objects.select_related("signed_by"):
        role = ""
        if signature.signed_by_id and signature.signed_by:
            role = signature.signed_by.get_role_display()
        if not role:
            role = signature.signer_title or ""
        DocumentSignature.objects.filter(pk=signature.pk).update(signer_role=role)


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0042_auditlog_logistics_a_timesta_ad09de_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentsignature",
            name="signer_role",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.RunPython(populate_signer_role, migrations.RunPython.noop),
    ]
