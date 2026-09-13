from django.db import migrations


def create_locales(apps, schema_editor):
    Locale = apps.get_model("wagtailcore.Locale")
    for language_code in ("en", "es", "ar", "ko"):
        Locale.objects.get_or_create(language_code=language_code)


def remove_locales(apps, schema_editor):
    Locale = apps.get_model("wagtailcore.Locale")
    Locale.objects.filter(language_code__in=("en", "es", "ar", "ko")).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0002_create_homepage"),
    ]

    operations = [
        migrations.RunPython(create_locales, remove_locales),
    ]
