"""
Crée la page « l'agence » de resdigita.org (cms.AgencyPage), sous la page d'accueil Numérique (cms.NumeriquePage).

    manage.py creer_agence               # simulation : rapport seulement
    manage.py creer_agence --appliquer   # crée

Idempotent.
"""
from django.core.management.base import BaseCommand
from wagtail.models import Locale

from cms.models import AgencyPage, NumeriquePage

TITRE = "Resdigita, agence numérique des Grands Voisins"
LEAD = (
    "Resdigita est l'agence numérique des Grands Voisins : avec les personnes, pour les personnes. "
    "Nous concevons et faisons vivre des outils libres, sobres et accueillants."
)
MESSAGE = (
    "<p>Le numérique devrait rapprocher, pas éloigner. Chez Resdigita, nous en faisons un métier au service "
    "de la vie réelle : des outils que l'on comprend, que l'on peut garder, et qui ne vendent rien de vous.</p>"
)
CORPS = [
    ("prose", "<h2>Qui nous sommes</h2><p>Resdigita est portée par Les Grands Voisins, association coopérative "
              "d'intérêt général. Nous sommes des voisins — développeur·se·s, graphistes, animateur·rice·s "
              "d'ateliers — qui mettons une compétence numérique au service de la communauté et des associations.</p>"),
    ("prose", "<h2>Ce que nous faisons</h2><p><strong>Fabrique web</strong> : sites, comptes et services, sans "
              "traqueur. <strong>Outils auto-hébergés</strong> : courriel, visioconférence, listes, agenda, stockage "
              "— en logiciels libres. <strong>Ateliers et accompagnement</strong> : apprendre à se servir des outils, "
              "réparer, découvrir le libre. <strong>Soutien aux associations</strong> : mutualiser, monter un service, "
              "penser un projet numérique.</p>"),
    ("prose", "<h2>Notre manière de travailler</h2><p>Logiciels libres, aucun traceur, sobriété, consentement "
              "explicite : rien n'est public sans accord. Les personnes d'abord — le numérique fait partie de la vie "
              "réelle, il ne la remplace pas.</p>"),
    ("prose", "<h2>Pour qui</h2><p>Les voisins, les associations, et tout projet d'intérêt général. "
              "Écrivez-nous, nous vous répondons.</p>"),
]


class Command(BaseCommand):
    help = "Crée la page « l'agence » de resdigita.org."

    def add_arguments(self, parser):
        parser.add_argument("--appliquer", action="store_true", help="crée (sans cela : simulation)")

    def handle(self, *args, appliquer=False, **options):
        numerique = NumeriquePage.objects.first()
        if numerique is None:
            self.stdout.write("Pas de page d'accueil Numérique (resdigita.org) : lancer d'abord creer_site_resdigita.")
            return
        if AgencyPage.objects.first():
            self.stdout.write(f"La page « {TITRE} » existe déjà : rien à faire.")
            return
        self.stdout.write(f"  page « {TITRE} » : à créer sous « {numerique.title} »")
        if not appliquer:
            self.stdout.write("Simulation : rien n'a été écrit (--appliquer pour créer).")
            return
        numerique.add_child(instance=AgencyPage(
            title=TITRE, slug="agence", lead=LEAD, message=MESSAGE, body=CORPS,
            locale=Locale.objects.get(language_code="fr"), live=True,
        ))
        self.stdout.write("Page créée et publiée.")
