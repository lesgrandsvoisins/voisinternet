"""Étend le groupe « Administration » (0019) à la gestion des évènements (core.Event) et
à la validation des demandes de gestion d'évènement (core.EventManagementRequest)."""
from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

GROUP_NAME = "Administration"
PERMISSIONS = [
    ("core", "event", "view_event"),
    ("core", "event", "change_event"),
    ("core", "eventmanagementrequest", "view_eventmanagementrequest"),
    ("core", "eventmanagementrequest", "change_eventmanagementrequest"),
]


def add_permissions(apps, schema_editor):
    create_permissions(global_apps.get_app_config("core"), verbosity=0, using=schema_editor.connection.alias)

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    group = Group.objects.filter(name=GROUP_NAME).first()
    if group is None:
        return
    for app_label, model, codename in PERMISSIONS:
        content_type = ContentType.objects.get(app_label=app_label, model=model)
        group.permissions.add(Permission.objects.get(content_type=content_type, codename=codename))


def remove_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    group = Group.objects.filter(name=GROUP_NAME).first()
    if group is None:
        return
    for app_label, model, codename in PERMISSIONS:
        content_type = ContentType.objects.get(app_label=app_label, model=model)
        group.permissions.remove(Permission.objects.get(content_type=content_type, codename=codename))


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0027_event_managers_eventmanagementrequest"),
    ]

    operations = [
        migrations.RunPython(add_permissions, remove_permissions),
    ]
