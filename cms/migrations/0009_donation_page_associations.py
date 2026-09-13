from django.db import migrations

# Élargit l'argumentaire de la page Dons aux personnes morales (associations),
# jusque-là adressé seulement aux particuliers (cf. 0008_seed_more_pages).
OLD_LEAD = (
    "Soutenir Les Grands Voisins par son talent et sa volonté, par une participation "
    "économique, ou par un don de matériel : plusieurs façons de donner, sans rien "
    "attendre en retour."
)
NEW_LEAD = (
    "Soutenir Les Grands Voisins par son talent et sa volonté, par une participation "
    "économique, ou par un don de matériel : plusieurs façons de donner, à titre "
    "personnel ou associatif, sans rien attendre en retour."
)

OLD_FINANCIAL_CARD = "<p>Par adhésion annuelle, ou par don ponctuel : choisissez votre moyen.</p>"
NEW_FINANCIAL_CARD = (
    "<p>Par adhésion annuelle — ouverte aux personnes comme aux associations — "
    "ou par don ponctuel : choisissez votre moyen.</p>"
)


def set_lead_and_card(page, lead, financial_card_text):
    from wagtail.rich_text import RichText

    page.lead = lead
    for card in page.cards:
        if card.value["title"] == "Faire un don financier":
            card.value["text"] = RichText(financial_card_text)
    page.save_revision().publish()


def update_pages(apps, schema_editor):
    from cms.models import DonationPage

    page = DonationPage.objects.filter(slug="contributions").first()
    if page:
        set_lead_and_card(page, NEW_LEAD, NEW_FINANCIAL_CARD)


def revert_pages(apps, schema_editor):
    from cms.models import DonationPage

    page = DonationPage.objects.filter(slug="contributions").first()
    if page:
        set_lead_and_card(page, OLD_LEAD, OLD_FINANCIAL_CARD)


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0008_seed_more_pages"),
    ]

    operations = [
        migrations.RunPython(update_pages, revert_pages),
    ]
