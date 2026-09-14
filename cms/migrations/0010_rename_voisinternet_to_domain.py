from django.db import migrations

# Le site a perdu son identité propre « Voisinternet » : il est maintenant
# désigné par son domaine, lesgrandsvoisins.com (cf. 0002_create_homepage et
# 0006_seed_pole_pages pour le contenu d'origine).
OLD_HOME_TITLE = "Voisinternet"
NEW_HOME_TITLE = "lesgrandsvoisins.com"

OLD_NUAGE_CARD = (
    "<p>Remplacer les services des géants du web par des petits serveurs à la maison, "
    "peu gourmands en énergie, pour ses fichiers et ses photos. C'est très exactement "
    "ce que propose Voisinternet.</p>"
)
NEW_NUAGE_CARD = (
    "<p>Remplacer les services des géants du web par des petits serveurs à la maison, "
    "peu gourmands en énergie, pour ses fichiers et ses photos. C'est très exactement "
    "ce que propose lesgrandsvoisins.com.</p>"
)


def set_home_title(title):
    from cms.models import HomePage

    home = HomePage.objects.filter(slug="home").first()
    if home:
        home.title = title
        home.draft_title = title
        home.save_revision().publish()


def set_nuage_card(text):
    from wagtail.rich_text import RichText

    from cms.models import PolePage

    page = PolePage.objects.filter(slug="numerique").first()
    if page:
        for card in page.cards:
            if card.value["title"] == "Paris le Nuage":
                card.value["text"] = RichText(text)
        page.save_revision().publish()


def update_content(apps, schema_editor):
    set_home_title(NEW_HOME_TITLE)
    set_nuage_card(NEW_NUAGE_CARD)


def revert_content(apps, schema_editor):
    set_home_title(OLD_HOME_TITLE)
    set_nuage_card(OLD_NUAGE_CARD)


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0009_donation_page_associations"),
    ]

    operations = [
        migrations.RunPython(update_content, revert_content),
    ]
