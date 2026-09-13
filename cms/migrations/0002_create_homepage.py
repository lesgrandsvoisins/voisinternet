from django.db import migrations


def create_homepage(apps, schema_editor):
    # Les modèles historiques (apps.get_model) n'ont pas le save() de Page,
    # qui attribue la locale par défaut et gère l'arbre (treebeard) : on
    # importe donc les vraies classes pour cette migration de données.
    from django.contrib.contenttypes.models import ContentType
    from wagtail.models import Page, Site

    from cms.models import HomePage

    # Pas de Page.objects.filter(depth=2).delete() : le collecteur de Django
    # vérifie alors la table de CHAQUE sous-classe de Page connue du code
    # *actuel* (cms.models important toujours la même version), y compris
    # celles créées par des migrations cms plus récentes que celle-ci — sur
    # une base neuve, ces tables n'existent pas encore à ce point de
    # l'historique et la suppression échoue. Le SQL direct évite le
    # collecteur ; sûr ici car la page par défaut de Wagtail n'a jamais de
    # ligne dans une table de sous-classe.
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DELETE FROM wagtailcore_page WHERE depth = 2")

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

    # HomePage.objects.create() ci-dessus pose la page directement au chemin
    # de l'ancienne page supprimée, sans passer par add_child() : le
    # numchild de Root (mis à jour par le delete() de treebeard) n'est donc
    # pas réincrémenté. On répare l'arbre pour que les futurs add_child()
    # (ex. traductions) calculent le bon chemin.
    Page.fix_tree()


def remove_homepage(apps, schema_editor):
    # Même remarque : éviter le collecteur de Django (cf. create_homepage).
    # Ici la ligne supprimée a bien une ligne fille dans cms_homepage : on
    # la retire explicitement (pas de cascade en base, faite normalement
    # par le collecteur qu'on contourne).
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM cms_homepage WHERE page_ptr_id IN "
            "(SELECT id FROM wagtailcore_page WHERE depth = 2 AND slug = 'home')"
        )
        cursor.execute("DELETE FROM wagtailcore_page WHERE depth = 2 AND slug = 'home'")


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
