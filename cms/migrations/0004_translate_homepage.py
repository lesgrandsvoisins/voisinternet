from django.db import migrations

LANGUAGE_CODES = ("en", "es", "ar", "ko")


def create_translations(apps, schema_editor):
    # Comme pour 0002_create_homepage : Page.copy_for_translation() s'appuie
    # sur treebeard et sur la logique métier de Page, absente des modèles
    # historiques. On importe donc les vraies classes.
    from wagtail.models import Locale

    from cms.models import HomePage

    home = HomePage.objects.get(slug="home")

    for language_code in LANGUAGE_CODES:
        locale = Locale.objects.get(language_code=language_code)
        if home.has_translation(locale):
            continue
        translated = home.copy_for_translation(locale)
        translated.save_revision().publish()


def remove_translations(apps, schema_editor):
    from wagtail.models import Locale

    from cms.models import HomePage

    for language_code in LANGUAGE_CODES:
        try:
            locale = Locale.objects.get(language_code=language_code)
        except Locale.DoesNotExist:
            continue
        HomePage.objects.filter(locale=locale, slug__startswith="home").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0003_content_locales"),
    ]

    operations = [
        migrations.RunPython(create_translations, remove_translations),
    ]
