"""
Crée le site Wagtail de resdigita.org (« Numérique des Grands Voisins ») : une page d'accueil `NumeriquePage` à la racine de
l'arbre et un `Site` pour www.resdigita.org, sans toucher à l'arbre de lesgrandsvoisins.com.

    manage.py creer_site_resdigita               # simulation : rapport seulement
    manage.py creer_site_resdigita --appliquer   # crée

Idempotent. Le nom de domaine ne sert la page qu'une fois que l'administration a fait pointer www.resdigita.org vers
l'application (docs/SITE-RESDIGITA.md).
"""
from django.core.management.base import BaseCommand
from wagtail.models import Locale, Page, Site

from cms.models import NumeriquePage

HOTE = "www.resdigita.org"
MESSAGE = (
    "<p>Les personnes se retrouvent d'abord dans la vie réelle. L'ordinateur en fait partie : il aide à se rencontrer, "
    "à s'écrire, à s'organiser, à partager. Voici les outils numériques que les Grands Voisins mettent à disposition, "
    "en logiciels libres, hébergés par l'association.</p>"
)


class Command(BaseCommand):
    help = "Crée le site Wagtail de resdigita.org."

    def add_arguments(self, parser):
        parser.add_argument("--appliquer", action="store_true", help="crée (sans cela : simulation)")

    def handle(self, *args, appliquer=False, **options):
        page = NumeriquePage.objects.first()
        site = Site.objects.filter(hostname=HOTE).first()
        if page and site and site.root_page_id == page.pk:
            self.stdout.write("Le site resdigita.org existe déjà : rien à faire.")
            return
        self.stdout.write(f"  {'page « Numérique des Grands Voisins » : existe' if page else 'page « Numérique des Grands Voisins » : à créer'}")
        self.stdout.write(f"  {'site ' + HOTE + ' : existe (racine à rattacher)' if site else 'site ' + HOTE + ' : à créer'}")
        if not appliquer:
            self.stdout.write("Simulation : rien n'a été écrit (--appliquer pour créer).")
            return
        if page is None:
            racine = Page.get_first_root_node()
            page = racine.add_child(instance=NumeriquePage(
                title="Numérique des Grands Voisins", slug="numerique", message=MESSAGE,
                locale=Locale.objects.get(language_code="fr"), live=True,
            ))
        if site is None:
            Site.objects.create(hostname=HOTE, port=443, site_name="Numérique des Grands Voisins", root_page=page)
        else:
            site.root_page = page
            site.save()
        self.stdout.write("Site créé.")
