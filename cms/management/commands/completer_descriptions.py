"""
Remplit la description pour les moteurs de recherche (`search_description`) des pages publiées qui n'en ont pas, avec le début
de leur texte (chapeau, introduction ou corps), coupé proprement à ~155 caractères. Ne remplace jamais une description
existante et ne touche pas une page qui a des modifications non publiées (on ne publierait pas le brouillon de quelqu'un).

    manage.py completer_descriptions              # simulation : liste ce qui serait posé
    manage.py completer_descriptions --appliquer  # écrit (nouvelle révision publiée par page)
"""
import re

from django.core.management.base import BaseCommand
from django.utils.html import strip_tags
from wagtail.models import Page

CHAMPS = ("excerpt", "lead", "intro", "summary", "body", "cards", "description")
LONGUEUR = 155


def texte_de(page):
    for nom in CHAMPS:
        valeur = getattr(page, nom, None)
        if not valeur:
            continue
        try:
            brut = str(valeur)
        except Exception:
            continue
        texte = re.sub(r"\s+", " ", strip_tags(brut.replace("<", " <"))).strip()
        if len(texte) >= 40:
            return texte
    return ""


def coupe(texte):
    if len(texte) <= LONGUEUR:
        return texte
    morceau = texte[:LONGUEUR].rsplit(" ", 1)[0].rstrip(" ,;:.-–—")
    return morceau + "…"


class Command(BaseCommand):
    help = "Remplit les descriptions manquantes (SEO) des pages publiées avec le début de leur texte."

    def add_arguments(self, parser):
        parser.add_argument("--appliquer", action="store_true", help="Écrire (sinon simulation)")

    def handle(self, *args, appliquer, **options):
        posees = sans_texte = brouillons = 0
        for page in Page.objects.live().exclude(depth=1).order_by("path").specific():
            if page.search_description:
                continue
            if page.has_unpublished_changes:
                brouillons += 1
                continue
            description = coupe(texte_de(page))
            if not description:
                sans_texte += 1
                continue
            posees += 1
            self.stdout.write(f"{page.url_path} : {description}")
            if appliquer:
                page.search_description = description
                page.save_revision().publish()
        self.stdout.write(self.style.SUCCESS(
            f"{posees} description(s) {'posée(s)' if appliquer else 'à poser (--appliquer)'} ; {sans_texte} page(s) sans texte "
            f"exploitable ; {brouillons} page(s) avec modifications non publiées laissée(s)."))
