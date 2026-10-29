"""
Importe dans le blog Wagtail les « pages » (et non les billets) de l'export JSON de l'ancien blog Ghost : par défaut les
Gazettes Voisines (`gazette`, `gazette-1` … `gazette-11`), jamais reprises avec les billets (`import_ghost_posts`).

    manage.py import_ghost_pages /chemin/blog-des-grands-voisins.ghost.<date>.json [--slugs a,b] [--publier]

Les articles sont créés en BROUILLON (relecture avant publication) sauf avec --publier. Idempotent : une page dont
l'identifiant existe déjà est laissée telle quelle. Les images ne sont pas dans l'export JSON : leurs adresses pointent
vers MEDIA_URL/ghost-import/images/… ; copier les fichiers de `content/images/` du serveur Ghost dans
MEDIA_ROOT/ghost-import/images/ (même arborescence) pour qu'elles s'affichent.
"""
import json
import re
from pathlib import Path

import bleach
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime
from wagtail.models import Locale

from cms.models import BlogIndexPage, BlogPostPage
from core.views import OLD_BLOG_RENAMED

GAZETTES = ["gazette"] + [f"gazette-{n}" for n in range(1, 12)]
ALLOWED_TAGS = ["p", "br", "hr", "strong", "em", "b", "i", "s", "a", "ul", "ol", "li", "blockquote", "h2", "h3", "h4", "img"]
ALLOWED_ATTRIBUTES = {"a": ["href", "title"], "img": ["src", "alt", "title"]}


def convertir(html, slugs_blog):
    """HTML de Ghost -> HTML que l'éditeur riche de Wagtail sait relire (sans les cartes « kg-… » de Ghost)."""
    # Carte de lien (signet) -> un simple lien.
    def signet(m):
        bloc = m.group(0)
        href = re.search(r'href="([^"]+)"', bloc)
        titre = re.search(r'kg-bookmark-title">(.*?)</div>', bloc, re.S)
        if not href:
            return ""
        return f'<p><a href="{href.group(1)}">{(titre.group(1) if titre else href.group(1)).strip()}</a></p>'

    html = re.sub(r'<figure class="kg-card kg-bookmark-card">.*?</figure>', signet, html, flags=re.S)
    html = re.sub(r"</?figure[^>]*>", "", html)
    html = re.sub(r"<figcaption>(.*?)</figcaption>", r"<p><em>\1</em></p>", html, flags=re.S)
    media = settings.MEDIA_URL.rstrip("/")
    html = re.sub(r"__GHOST_URL__/content/images/(?:size/w\d+(?:h\d+)?/)?", f"{media}/ghost-import/images/", html)
    html = re.sub(r"__GHOST_URL__/content/(files|media)/", f"{media}/ghost-import/files/", html)
    # Lien vers un autre billet ou une autre page de Ghost -> son adresse ici (liens à l'intérieur du blog).
    html = re.sub(r'__GHOST_URL__/([a-z0-9-]+)/?(?=["#?])', lambda m: f"/fr/blog/{OLD_BLOG_RENAMED.get(m.group(1), m.group(1))}/", html)
    html = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, protocols=["http", "https", "mailto"], strip=True)
    # L'éditeur riche exige des balises vides fermées (voir import_ghost_posts.self_close_void_tags).
    return re.sub(r"<(img|br)((?:\s+[^<>]*)?)(?<!/)>", r"<\1\2/>", html)


class Command(BaseCommand):
    help = "Importe les pages Ghost (par défaut les Gazettes Voisines) comme billets de blog, en brouillon."

    def add_arguments(self, parser):
        parser.add_argument("export", help="Export JSON de Ghost")
        parser.add_argument("--slugs", default=",".join(GAZETTES), help="Identifiants à importer, séparés par des virgules")
        parser.add_argument("--publier", action="store_true", help="Publier directement (sinon brouillon)")

    def handle(self, *args, export, slugs, publier, **options):
        chemin = Path(export)
        if not chemin.is_file():
            raise CommandError(f"Fichier introuvable : {chemin}")
        data = json.loads(chemin.read_text(encoding="utf-8"))["db"][0]["data"]
        voulus = [s.strip() for s in slugs.split(",") if s.strip()]
        par_slug = {p["slug"]: p for p in data["posts"] if p["status"] == "published"}
        slugs_blog = set(par_slug)
        index = BlogIndexPage.objects.filter(locale=Locale.get_default()).first()
        if index is None:
            raise CommandError("Page d'index du blog introuvable.")
        crees = presents = 0
        for slug in voulus:
            p = par_slug.get(slug)
            if p is None:
                self.stderr.write(f"absent de l'export (ou non publié) : {slug}")
                continue
            if BlogPostPage.objects.filter(slug=slug).exists():
                presents += 1
                continue
            texte = re.sub(r"<[^>]+>", " ", p["html"] or "")
            chapeau = (p.get("custom_excerpt") or re.sub(r"\s+", " ", texte).strip())[:300]
            page = BlogPostPage(
                title=p["title"], draft_title=p["title"], slug=slug, live=False,
                date=parse_datetime(p["published_at"]), excerpt=chapeau,
                body=convertir(p["html"] or "", slugs_blog),
            )
            index.add_child(instance=page)
            revision = page.save_revision()
            if publier:
                revision.publish()
            crees += 1
            self.stdout.write(f"importé ({'publié' if publier else 'brouillon'}) : {slug}")
        self.stdout.write(self.style.SUCCESS(f"{crees} page(s) importée(s), {presents} déjà présente(s)."))
