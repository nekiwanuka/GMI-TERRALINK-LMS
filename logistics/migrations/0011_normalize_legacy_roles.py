from django.db import migrations


def normalize_legacy_roles(apps, schema_editor):
    CustomUser = apps.get_model("logistics", "CustomUser")
    role_map = {
        "superuser": "ADMIN",
        "data_entry": "OFFICE_ADMIN",
    }
    for old_role, new_role in role_map.items():
        CustomUser.objects.filter(role=old_role).update(role=new_role)


def revert_legacy_roles(apps, schema_editor):
    CustomUser = apps.get_model("logistics", "CustomUser")
    role_map = {
        "ADMIN": "superuser",
        "OFFICE_ADMIN": "data_entry",
    }
    for new_role, old_role in role_map.items():
        CustomUser.objects.filter(role=new_role).update(role=old_role)


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0010_productionline_alter_customuser_role_transaction_and_more"),
    ]

    operations = [
        migrations.RunPython(normalize_legacy_roles, revert_legacy_roles),
    ]
