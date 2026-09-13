from django.db import migrations

# Reprise du contenu jusque-là codé en dur dans core/templates/core/{grandsvoisins,
# contact,contributions}.html, avant leur passage sous Wagtail (voir aussi
# 0006_seed_pole_pages pour civisme/arts-plastiques/numérique).
CONTACT_EMAIL = "contact@voisinter.net"


def create_pages(apps, schema_editor):
    from cms.models import AssociationPage, ContactPage, DonationPage, HomePage

    home = HomePage.objects.get(slug="home")

    if not ContactPage.objects.filter(slug="contact").exists():
        page = ContactPage(
            title="Contact",
            draft_title="Contact",
            slug="contact",
            lead="Une question, un problème : écrivez-nous. Un voisin vous répond, pas un robot.",
            cards=[
                {"type": "card", "value": {
                    "title": "Par courriel",
                    "text": (
                        f'<p>Écrivez-nous directement à <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>. '
                        "Nous répondons en quelques jours.</p>"
                    ),
                }},
                {"type": "card", "value": {
                    "title": "Aux Conseils des Voisins",
                    "text": '<p>Un rendez-vous périodique et ouvert à tous : consultez <a href="/fr/agenda/">l\'agenda</a>.</p>',
                }},
                {"type": "card", "value": {
                    "title": "Devenir bénévole",
                    "text": (
                        '<p>Donner du temps, un talent, ou un coup de main : voyez '
                        '<a href="/fr/contributions/">nos contributions</a>.</p>'
                    ),
                }},
            ],
        )
        home.add_child(instance=page)
        page.save_revision().publish()

    if not AssociationPage.objects.filter(slug="grandsvoisins").exists():
        page = AssociationPage(
            title="Association",
            draft_title="Association",
            slug="grandsvoisins",
            lead=(
                "Voisinternet est un programme porté par l'association coopérative Les Grands "
                "Voisins : une conscience collective à laquelle chacun contribue. Nous demandons "
                "votre confiance : voici de quoi la vérifier."
            ),
            body=[
                {"type": "card", "value": {
                    "title": "Notre raison d'être",
                    "text": (
                        "<p>Écrite collectivement par une centaine de personnes en 2017, notre "
                        "raison d'être vient des interstices du béton et des politiques publiques : "
                        "nous croyons aux ponts entre l'utopie et le réel, et à l'accueil de "
                        "chacun.</p>"
                    ),
                }},
                {"type": "card", "value": {
                    "title": "D'où nous venons",
                    "text": (
                        "<p>Les Grands Voisins sont nés entre 2015 et 2017 à l'hôpital "
                        "Saint-Vincent-de-Paul, dans le 14ᵉ arrondissement de Paris, entre "
                        "Port-Royal et les Catacombes. Depuis, nous nous demandons si un lieu "
                        "physique est encore nécessaire pour rester voisins.</p>"
                    ),
                }},
                {"type": "board", "value": [
                    {"name": "Chris Mann", "role": "Président"},
                    {"name": "Sviatlana Viarbitskaya", "role": "Trésorière"},
                    {"name": "Caroline Lhomme", "role": "Vice-présidente"},
                ]},
                {"type": "card", "value": {
                    "title": "Statut légal",
                    "text": "<p>Association loi de 1901. RNA W751240710, SIREN 832760102.</p>",
                }},
                {"type": "documents", "value": [
                    {"label": "Statuts de l'association", "document": None},
                    {"label": "Comptes annuels", "document": None},
                    {"label": "Comptes rendus d'assemblée générale", "document": None},
                    {"label": "Nos engagements d'hébergeur", "document": None},
                ]},
            ],
        )
        home.add_child(instance=page)
        page.save_revision().publish()

    if not DonationPage.objects.filter(slug="contributions").exists():
        page = DonationPage(
            title="Dons",
            draft_title="Dons",
            slug="contributions",
            lead=(
                "Soutenir Les Grands Voisins par son talent et sa volonté, par une participation "
                "économique, ou par un don de matériel : plusieurs façons de donner, sans rien "
                "attendre en retour."
            ),
            cards=[
                {"type": "card", "value": {
                    "title": "Donner du temps",
                    "text": (
                        "<p>Animer un atelier, relire le guide, dépanner un voisin, ou simplement "
                        f'être présent : chacun donne le temps qu\'il veut. Écrivez-nous à '
                        f'<a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>'
                    ),
                }},
                {"type": "card", "value": {
                    "title": "Faire un don financier",
                    "text": "<p>Par adhésion annuelle, ou par don ponctuel : choisissez votre moyen.</p>",
                }},
                {"type": "card", "value": {
                    "title": "Donner du matériel",
                    "text": "<p>[À compléter : matériel accepté, effacement des données, lieu de dépôt.]</p>",
                }},
            ],
        )
        home.add_child(instance=page)
        page.save_revision().publish()


def remove_pages(apps, schema_editor):
    from cms.models import AssociationPage, ContactPage, DonationPage

    ContactPage.objects.filter(slug="contact").delete()
    AssociationPage.objects.filter(slug="grandsvoisins").delete()
    DonationPage.objects.filter(slug="contributions").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0007_associationpage_contactpage_donationpage"),
    ]

    operations = [
        migrations.RunPython(create_pages, remove_pages),
    ]
