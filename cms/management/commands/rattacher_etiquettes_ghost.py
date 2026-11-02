"""
Rattache aux articles du blog (cms.BlogPostPage) les étiquettes qu'ils avaient dans Ghost : l'import des articles
(import_ghost_posts, depuis les fichiers Markdown) ne les portait pas. Lit deploy/ghost-export/blog.json (`posts_tags`).

    manage.py rattacher_etiquettes_ghost               # simulation : rapport seulement
    manage.py rattacher_etiquettes_ghost --appliquer   # rattache

N'ajoute que des étiquettes publiques (les étiquettes internes de Ghost, « #… », sont ignorées), crée l'étiquette `core.Tag`
si elle manque, ne retire rien, ne touche qu'aux articles déjà importés (même adresse). Idempotent.
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import translation
from django.utils.text import slugify

from cms.models import BlogPostPage
from core.models import Tag

EXPORT = Path(settings.BASE_DIR) / "deploy" / "ghost-export" / "blog.json"


def trouver_ou_creer(slug, nom):
    """L'étiquette du site de même adresse, sinon de même nom (sans tenir compte des majuscules : « Arts platiques » existait
    déjà sous une autre adresse), sinon une nouvelle."""
    with translation.override("fr"):
        tag = Tag.objects.filter(slug=slug).first() or Tag.objects.filter(name__iexact=nom).first()
        return tag or Tag.objects.create(slug=slug, name=nom)


class Command(BaseCommand):
    help = "Rattache aux articles importés les étiquettes qu'ils avaient dans Ghost."

    def add_arguments(self, parser):
        parser.add_argument("--appliquer", action="store_true", help="écrit (sans cela : simulation)")
        parser.add_argument("--fichier", default=str(EXPORT), help="export Ghost (blog.json)")

    def handle(self, *args, appliquer=False, fichier=None, **options):
        data = json.loads(Path(fichier).read_text(encoding="utf-8"))
        data = data["db"][0]["data"] if "db" in data else data["data"]
        etiquettes = {t["id"]: t for t in data["tags"] if t.get("visibility") == "public"}
        articles = {p["id"]: p["slug"] for p in data["posts"] if p["status"] == "published"}
        par_article = {}
        for lien in data["posts_tags"]:
            if lien["tag_id"] in etiquettes and lien["post_id"] in articles:
                par_article.setdefault(articles[lien["post_id"]], []).append(etiquettes[lien["tag_id"]])
        ajouts = absents = 0
        for slug, tags in sorted(par_article.items()):
            page = BlogPostPage.objects.filter(slug=slug).first()
            if page is None:
                absents += 1
                continue
            deja = set(page.tags.values_list("slug", flat=True))
            for t in tags:
                tslug = t["slug"] or slugify(t["name"])
                if tslug in deja:
                    continue
                ajouts += 1
                self.stdout.write(f"  {slug} : #{tslug}")
                if appliquer:
                    tag = trouver_ou_creer(tslug, t["name"])
                    page.tags.add(tag)
        self.stdout.write(f"{ajouts} étiquette(s) {'rattachée(s)' if appliquer else 'à rattacher'} ; "
                          f"{absents} article(s) de l'export absent(s) du site.")
        if ajouts and not appliquer:
            self.stdout.write("Simulation : rien n'a été écrit (--appliquer pour rattacher).")
