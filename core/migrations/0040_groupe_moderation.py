"""Groupe « Modération » : les personnes qui décident des demandes (core.Demande) — distinct du groupe « Administration »."""
from django.db import migrations

GROUP_NAME = "Modération"


def create_group(apps, schema_editor):
    apps.get_model("auth", "Group").objects.get_or_create(name=GROUP_NAME)


class Migration(migrations.Migration):
    dependencies = [("core", "0039_demandes"), ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(create_group, migrations.RunPython.noop)]
