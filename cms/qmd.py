"""
Export/import individuel d'un article de blog (cms.BlogPostPage) au format .qmd (Quarto
Markdown) — un fichier par langue. Utilisé par les commandes de gestion
export_blog_qmd/import_blog_qmd (cms/management/commands/) et par les boutons
Exporter/Importer .qmd de l'écran d'édition Wagtail (cms/wagtail_hooks.py), pour éditer
des articles avec des outils Quarto externes.

Le frontmatter YAML porte `key` (BlogPostPage.translation_key, le même pour toutes les
traductions d'un même article) et `lang` (le code de la locale) : c'est cette paire, pas
le slug ni le pk, qui identifie l'article au réimport — round-trip stable même si le
titre ou le slug changent entre temps. Sans traduction existante pour cette langue mais
une autre langue déjà présente pour la même clé, l'import crée la traduction Wagtail
(Page.copy_for_translation) plutôt qu'un article indépendant.

Une image (ou un document, ou un lien vers une page interne) inséré via les outils
Wagtail du texte enrichi est stocké en base sous une forme abstraite (<embed
embedtype="image" id="…">, <a linktype="document" id="…">, <a linktype="page" id="…">),
pas comme un simple <img src="…">/<a href="…"> : l'identifiant Wagtail est donc porté
dans le "title" du Markdown (ex. `![alt](url "wagtail-image:123:fullwidth")`), un attribut
que Quarto ignore superficiellement (il reste un lien/une image valides pour la lecture
et l'édition du texte) mais que l'import sait reconnaître pour reconstruire l'embed
d'origine — l'image redevient alors gérée par le sélecteur d'image de Draftail, pas un
simple <img> figé. Sans cet identifiant (image/document déjà supprimé, ou contenu écrit à
la main dans l'éditeur Quarto), l'URL absolue reste utilisée telle quelle.
"""
import re
from datetime import date as date_cls
from datetime import datetime as datetime_cls
from html import escape
from html.parser import HTMLParser

import yaml
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.text import slugify
from wagtail.models import Locale, Page, Site

from core.templatetags.markdown_filters import markdown_filter

from .models import BlogIndexPage, BlogPostPage

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n?(.*)\Z", re.DOTALL)
PAGEBREAK_SHORTCODE = "{{< pagebreak >}}"


def _absolute_url(path):
    """Les URL résolues (images, documents, pages) sont parfois relatives (/media/…,
    /documents/…) : on les préfixe par l'hôte du site par défaut pour qu'elles restent
    valides hors du site (ouvertes dans un éditeur Quarto local, par exemple)."""
    if not path or path.startswith(("http://", "https://", "mailto:", "tel:")):
        return path
    site = Site.objects.filter(is_default_site=True).first()
    return f"{site.root_url}{path}" if site else path


def _resolve_image_url(image_id):
    from wagtail.images.models import Image

    try:
        image = Image.objects.get(pk=image_id)
    except (Image.DoesNotExist, ValueError, TypeError):
        return ""
    return _absolute_url(image.get_rendition("width-1600").url)


def _resolve_document_url(document_id):
    from wagtail.documents.models import Document

    try:
        document = Document.objects.get(pk=document_id)
    except (Document.DoesNotExist, ValueError, TypeError):
        return ""
    return _absolute_url(document.url)


def _resolve_page_url(page_id):
    try:
        page = Page.objects.get(pk=page_id)
    except (Page.DoesNotExist, ValueError, TypeError):
        return ""
    return page.full_url or ""


def _self_close_void_tags(html):
    """Même besoin que cms/management/commands/import_ghost_posts.py::self_close_void_tags :
    Draftail (l'éditeur riche de Wagtail) exige <img .../> et <br/> fermés pour relire un
    article en édition, alors que markdown_filter (bleach) les rend non refermés."""
    return re.sub(r"<(img|br)((?:\s+[^<>]*)?)(?<!/)>", r"<\1\2/>", html)


class _HTMLToMarkdown(HTMLParser):
    """
    Convertisseur volontairement minimal : couvre exactement le sous-ensemble de balises
    que BlogPostPage.body (RichTextField) peut produire — gras/italique, h2-h4, listes,
    liens (externes, page, document), images (dont les entités Wagtail <embed>), <hr>
    (séparateur ou saut de page). Pas une bibliothèque HTML→Markdown généraliste : le
    format d'entrée est entièrement sous notre contrôle (cms/models.py:BlogPostPage.body
    features=). Travaille directement sur le HTML tel que stocké en base (pas
    wagtail.rich_text.expand_db_html) pour garder les identifiants image/document/page,
    perdus par expand_db_html — voir _resolve_*_url ci-dessus et le docstring du module.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.list_stack = []
        self.link_href = None
        self.link_title_marker = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "br":
            self.out.append("  \n")
        elif tag == "hr":
            self._ensure_blank_line()
            if "pagebreak" in (attrs.get("class") or ""):
                self.out.append(f"{PAGEBREAK_SHORTCODE}\n\n")
            else:
                self.out.append("---\n\n")
        elif tag in ("strong", "b"):
            self.out.append("**")
        elif tag in ("em", "i"):
            self.out.append("*")
        elif tag in ("h2", "h3", "h4"):
            self._ensure_blank_line()
            self.out.append("#" * int(tag[1]) + " ")
        elif tag == "ul":
            self.list_stack.append(["ul", 0])
        elif tag == "ol":
            self.list_stack.append(["ol", 0])
        elif tag == "li":
            if self.list_stack:
                self.list_stack[-1][1] += 1
                kind, count = self.list_stack[-1]
                indent = "  " * (len(self.list_stack) - 1)
                marker = "-" if kind == "ul" else f"{count}."
                self._ensure_newline()
                self.out.append(f"{indent}{marker} ")
        elif tag == "a":
            linktype, link_id = attrs.get("linktype"), attrs.get("id")
            if linktype == "document" and link_id:
                self.link_href = _resolve_document_url(link_id)
                self.link_title_marker = f"wagtail-document:{link_id}"
            elif linktype == "page" and link_id:
                self.link_href = _resolve_page_url(link_id)
                self.link_title_marker = f"wagtail-page:{link_id}"
            else:
                self.link_href = _absolute_url(attrs.get("href", ""))
                self.link_title_marker = None
            self.out.append("[")
        elif tag == "img":
            self._ensure_blank_line()
            self.out.append(f"![{attrs.get('alt', '')}]({_absolute_url(attrs.get('src', ''))})\n\n")
        elif tag == "embed" and attrs.get("embedtype") == "image" and attrs.get("id"):
            self._ensure_blank_line()
            marker = f"wagtail-image:{attrs['id']}:{attrs.get('format', '')}"
            self.out.append(f'![{attrs.get("alt", "")}]({_resolve_image_url(attrs["id"])} "{marker}")\n\n')
        elif tag == "embed":
            # embedtype="image" traité ci-dessus ; les autres (embedtype="media", vidéos
            # oEmbed…) sont rares dans ce blog — on garde au moins l'URL brute plutôt que
            # de la perdre silencieusement.
            url = attrs.get("url", "")
            if url:
                self._ensure_blank_line()
                self.out.append(f"<{url}>\n\n")

    def handle_endtag(self, tag):
        if tag == "p":
            self._ensure_blank_line()
        elif tag in ("strong", "b", "em", "i"):
            self.out.append("**" if tag in ("strong", "b") else "*")
        elif tag in ("h2", "h3", "h4"):
            self.out.append("\n\n")
        elif tag in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop()
            self._ensure_blank_line()
        elif tag == "li":
            self._ensure_newline()
        elif tag == "a":
            if self.link_title_marker:
                self.out.append(f']({self.link_href} "{self.link_title_marker}")')
            else:
                self.out.append(f"]({self.link_href})")
            self.link_href = None
            self.link_title_marker = None

    def handle_data(self, data):
        self.out.append(data)

    def _ensure_newline(self):
        if self.out and not "".join(self.out[-1:]).endswith("\n"):
            self.out.append("\n")

    def _ensure_blank_line(self):
        text = "".join(self.out)
        if text and not text.endswith("\n\n"):
            if not text.endswith("\n"):
                self.out.append("\n")
            self.out.append("\n")

    def result(self):
        text = "".join(self.out)
        return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def export_blogpost_qmd(page):
    """Sérialise un BlogPostPage (une langue) en texte .qmd."""
    converter = _HTMLToMarkdown()
    converter.feed(page.body)

    front = {
        "title": page.title,
        "key": str(page.translation_key),
        "lang": page.locale.language_code,
        "date": page.date.isoformat(),
        "author": page.author_name,
        "excerpt": page.excerpt,
        "slug": page.slug,
        "featured": page.featured,
        "tags": list(page.tags.order_by("name").values_list("name", flat=True)),
        "url": page.full_url,
    }
    if page.featured_image_id:
        front["featured_image"] = _absolute_url(page.featured_image.get_rendition("width-1600").url)

    frontmatter = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return f"---\n{frontmatter}---\n\n{converter.result()}"


class _RestoreWagtailEmbeds(HTMLParser):
    """
    Pendant inverse de _HTMLToMarkdown pour les images/liens marqués : reconstruit les
    <embed embedtype="image">/<a linktype="document"|"page"> d'origine à partir du
    marqueur "wagtail-image:ID:FORMAT"/"wagtail-document:ID"/"wagtail-page:ID" laissé
    dans l'attribut title par markdown_filter (qui l'a lui-même reçu du Markdown généré
    par export_blogpost_qmd). Tout le reste passe inchangé (get_starttag_text()).
    """

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out = []

    def _handle_tag(self, tag, attrs):
        attrs = dict(attrs)
        marker = attrs.get("title", "")
        if tag == "img" and marker.startswith("wagtail-image:"):
            _, image_id, image_format = (marker.split(":", 2) + [""])[:3]
            fmt_attr = f' format="{escape(image_format, quote=True)}"' if image_format else ""
            alt = escape(attrs.get("alt", ""), quote=True)
            self.out.append(f'<embed embedtype="image" id="{image_id}" alt="{alt}"{fmt_attr}/>')
            return True
        if tag == "a" and marker.startswith("wagtail-document:"):
            doc_id = marker.split(":", 1)[1]
            self.out.append(f'<a linktype="document" id="{doc_id}">')
            return True
        if tag == "a" and marker.startswith("wagtail-page:"):
            page_id = marker.split(":", 1)[1]
            self.out.append(f'<a linktype="page" id="{page_id}">')
            return True
        return False

    def handle_starttag(self, tag, attrs):
        if not self._handle_tag(tag, attrs):
            self.out.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        if not self._handle_tag(tag, attrs):
            self.out.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.out.append(f"</{tag}>")

    def handle_data(self, data):
        self.out.append(data)

    def handle_entityref(self, name):
        self.out.append(f"&{name};")

    def handle_charref(self, name):
        self.out.append(f"&#{name};")

    def result(self):
        return "".join(self.out)


def _restore_wagtail_embeds(html):
    restorer = _RestoreWagtailEmbeds()
    restorer.feed(html)
    return restorer.result()


def _parse_date(value):
    if isinstance(value, datetime_cls):
        return timezone.make_aware(value) if timezone.is_naive(value) else value
    if isinstance(value, date_cls):
        return timezone.make_aware(datetime_cls.combine(value, datetime_cls.min.time()))
    if value:
        parsed = parse_datetime(str(value))
        if parsed is None:
            parsed_date = parse_date(str(value))
            parsed = datetime_cls.combine(parsed_date, datetime_cls.min.time()) if parsed_date else None
        if parsed is not None:
            return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
    return timezone.now()


def import_blogpost_qmd(text):
    """
    Crée ou met à jour un BlogPostPage à partir d'un texte .qmd. Retourne la page
    publiée (save_revision().publish()).
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("Frontmatter YAML manquant (le fichier doit commencer par ---).")
    front = yaml.safe_load(match.group(1)) or {}
    body_md = match.group(2).replace(PAGEBREAK_SHORTCODE, '<hr class="pagebreak">')

    lang = front.get("lang") or "fr"
    locale = Locale.objects.get(language_code=lang)
    key = front.get("key")

    page = BlogPostPage.objects.filter(translation_key=key, locale=locale).first() if key else None
    if page is None:
        sibling = (
            BlogPostPage.objects.filter(translation_key=key).exclude(locale=locale).first() if key else None
        )
        page = sibling.copy_for_translation(locale, copy_parents=True) if sibling else BlogPostPage(locale=locale)
        if key and not page.pk:
            page.translation_key = key

    page.title = front.get("title") or page.title or front.get("slug") or ""
    page.slug = front.get("slug") or slugify(page.title)
    page.date = _parse_date(front.get("date"))
    page.author_name = front.get("author") or ""
    page.excerpt = (front.get("excerpt") or "")[:300]
    page.featured = bool(front.get("featured", False))
    body_html = _restore_wagtail_embeds(markdown_filter(body_md))
    page.body = _self_close_void_tags(body_html)

    is_new = page.pk is None
    if is_new:
        blog_index = BlogIndexPage.objects.filter(locale=locale).first()
        if blog_index is None:
            raise ValueError(f"Aucune BlogIndexPage en langue « {lang} » pour y rattacher l'article.")
        blog_index.add_child(instance=page)
    page.save_revision().publish()

    tags = front.get("tags") or []
    if tags:
        from core.models import Tag

        page.tags.set([Tag.objects.get_or_create(name=t, defaults={"slug": slugify(t)})[0] for t in tags])

    return page
