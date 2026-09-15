"""
Groupe « Administration » : les personnes qui en font partie peuvent valider les
raccourcis en attente (Service.requires_approval, Shortcut.approved) et la publication
des fiches de l'annuaire (DirectoryEntry.approved) — voir core/views.py et core/admin.py.
"""
from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

GROUP_NAME = "Administration"
PERMISSIONS = [
    ("core", "shortcut", "view_shortcut"),
    ("core", "shortcut", "change_shortcut"),
    ("core", "directoryentry", "view_directoryentry"),
    ("core", "directoryentry", "change_directoryentry"),
]


def create_group(apps, schema_editor):
    # Les permissions par défaut (view_*/change_*…) ne sont créées par Django qu'après
    # coup, une fois toute la migration terminée (signal post_migrate) — trop tard pour
    # les lire ici sans ce coup de pouce explicite (motif documenté par Django lui-même
    # pour créer un groupe avec permissions dans une migration de données).
    create_permissions(global_apps.get_app_config("core"), verbosity=0, using=schema_editor.connection.alias)

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    group, _created = Group.objects.get_or_create(name=GROUP_NAME)
    perms = []
    for app_label, model, codename in PERMISSIONS:
        content_type = ContentType.objects.get(app_label=app_label, model=model)
        perms.append(Permission.objects.get(content_type=content_type, codename=codename))
    group.permissions.set(perms)


def remove_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name=GROUP_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0018_directoryentry_approved_service_requires_approval_and_more"),
        ("auth", "0001_initial"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(create_group, remove_group),
    ]
