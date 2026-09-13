from django.db import migrations


def create_homepage(apps, schema_editor):
    # Les modèles historiques (apps.get_model) n'ont pas le save() de Page,
    # qui attribue la locale par défaut et gère l'arbre (treebeard) : on
    # importe donc les vraies classes pour cette migration de données.
    from django.contrib.contenttypes.models import ContentType
    from wagtail.models import Page, Site

    from cms.models import HomePage

    Page.objects.filter(depth=2).delete()

    content_type, __ = ContentType.objects.get_or_create(
        model="homepage", app_label="cms"
    )

    homepage = HomePage.objects.create(
        title="Voisinternet",
        draft_title="Voisinternet",
        slug="home",
        content_type=content_type,
        path="00010001",
        depth=2,
        numchild=0,
        url_path="/",
    )

    Site.objects.update_or_create(
        is_default_site=True,
        defaults={"hostname": "localhost", "root_page": homepage},
    )


def remove_homepage(apps, schema_editor):
    from cms.models import HomePage

    HomePage.objects.filter(slug="home").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0001_initial"),
        ("wagtailcore", "0098_apitoken"),
        ("wagtailsearch", "0010_add_text_fields"),
        ("wagtailforms", "0005_alter_formsubmission_form_data"),
    ]

    operations = [
        migrations.RunPython(create_homepage, remove_homepage),
    ]
