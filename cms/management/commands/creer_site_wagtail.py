"""
Crée un site Wagtail pour un ou plusieurs noms de domaine : une page d'accueil (`HomePage`) à la racine de l'arbre et un `Site` par nom,
sans toucher à l'arbre de lesgrandsvoisins.com. Wagtail choisit le site d'après le nom de domaine de la requête (table Site) :
tant qu'un nom n'a pas son Site, il retombe sur le site par défaut, donc sur l'accueil de lesgrandsvoisins.com.

    manage.py creer_site_wagtail Max max.resdigita.org max.lesgrandsvoisins.com               # simulation
    manage.py creer_site_wagtail Max max.resdigita.org max.lesgrandsvoisins.com --appliquer   # crée

Plusieurs noms partagent la même page d'accueil (même contenu). Idempotent : un nom déjà rattaché à une page n'est pas déplacé.
Le nom doit aussi être autorisé côté Django (DJANGO_ALLOWED_HOSTS, DJANGO_CSRF_TRUSTED_ORIGINS) et déclaré dans Caddy et Keycloak.
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify
from wagtail.models import Locale, Page, Site

from cms.models import HomePage


class Command(BaseCommand):
    help = "Crée un site Wagtail (page d'accueil + noms de domaine)."

    def add_arguments(self, parser):
        parser.add_argument("titre", help="titre de la page d'accueil du site (ex. Max)")
        parser.add_argument("hotes", nargs="+", help="noms de domaine (ex. max.resdigita.org)")
        parser.add_argument("--appliquer", action="store_true", help="crée (sans cela : simulation)")

    def handle(self, *args, titre, hotes, appliquer=False, **options):
        hotes = [h.strip().lower() for h in hotes]
        for h in hotes:
            if "." not in h or "/" in h or " " in h:
                raise CommandError(f"nom de domaine invalide : {h}")
        slug = slugify(titre) or "site"
        page = HomePage.objects.filter(slug=slug, depth=2).first() or Page.objects.filter(slug=slug, depth=2).first()
        self.stdout.write(f"  page d'accueil « {titre} » : {'existe' if page else 'à créer'}")
        existants = {h: Site.objects.filter(hostname=h).first() for h in hotes}
        for h, site in existants.items():
            self.stdout.write(f"  site {h} : {'existe' if site else 'à créer'}")
        if not appliquer:
            self.stdout.write("Simulation : rien n'a été écrit (--appliquer pour créer).")
            return
        if page is None:
            racine = Page.get_first_root_node()
            page = racine.add_child(instance=HomePage(
                title=titre, slug=slug, locale=Locale.objects.get(language_code="fr"), live=True,
            ))
        for h, site in existants.items():
            if site is None:
                Site.objects.create(hostname=h, port=443, site_name=titre, root_page=page)
        self.stdout.write("Site(s) créé(s).")
