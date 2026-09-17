"""
Export/import individuel d'un article de blog (cms.BlogPostPage) ou d'une page de
contenu (cms.ContentPage) au format .qmd (Quarto Markdown) — un fichier par langue.
Utilisé par les commandes de gestion export_blog_qmd/import_blog_qmd/
export_content_qmd/import_content_qmd (cms/management/commands/) et par les boutons
Exporter/Importer .qmd de l'écran d'édition Wagtail (cms/wagtail_hooks.py), pour éditer
des articles avec des outils Quarto externes.

Pour cms.ContentPage, l'isomorphisme avec Quarto va plus loin que pour le blog : les
callouts (::: {.callout-...}), tableaux et notes de bas de page ont un équivalent exact
dans les deux sens (voir cms.models.ContentPage/CalloutBlock, _split_content_blocks et
_ContentHTMLToMarkdown ci-dessous). Limite assumée : ces deux derniers arrivent
uniquement par import .qmd — Draftail (l'éditeur de texte enrichi Wagtail) n'a pas de
bouton pour créer ou modifier un tableau ou une note de bas de page, donc l'aller-retour
reste fidèle tant que personne ne retouche cette zone dans l'éditeur riche.

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
import zipfile
from datetime import date as date_cls
from datetime import datetime as datetime_cls
from html import escape
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path

import bleach
import markdown as md
import yaml
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.text import slugify
from wagtail.models import Locale, Page, Site

from core.templatetags.markdown_filters import markdown_filter

from .models import BlogIndexPage, BlogPostPage, ContentPage, PolePage

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n?(.*)\Z", re.DOTALL)
PAGEBREAK_SHORTCODE = "{{< pagebreak >}}"

# Liste blanche bleach dédiée à l'import de cms.ContentPage : les mêmes balises que
# core.templatetags.markdown_filters.markdown_filter (fiches de l'annuaire, contenu
# saisi en libre-service) plus tableaux/notes de bas de page (extension "extra" de
# python-markdown, voir _content_markdown_to_html) — jamais exposée aux comptes
# ordinaires, réservée au chemin d'import .qmd (cms/wagtail_hooks.py::_can_manage_qmd).
_CONTENT_ALLOWED_TAGS = [
    "p", "br", "hr", "strong", "em", "b", "i", "u", "s", "del",
    "a", "ul", "ol", "li", "blockquote", "code", "pre",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tr", "th", "td",
    "img", "span", "sup", "div",
]
_CONTENT_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "rel", "id"],
    "img": ["src", "alt", "title"],
    "li": ["id"],
    "sup": ["id"],
    "*": ["class"],
}
_CONTENT_ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

# Callout Quarto : ::: {.callout-note} … ::: (pas de callouts imbriqués — voir
# CalloutBlock, cms/models.py). Attribut title="…" facultatif, seule forme de titre
# reconnue (pas de première ligne "## Titre" traitée spécialement, pour rester simple).
_CALLOUT_OPEN_RE = re.compile(
    r'^:::+\s*\{\.callout-(note|tip|important|warning|caution)(?:\s+title="([^"]*)")?\s*\}\s*$'
)
_FENCE_CLOSE_RE = re.compile(r'^:::+\s*$')


def _content_markdown_to_html(text):
    html = md.markdown(text, extensions=["extra", "sane_lists"])
    return bleach.clean(
        html, tags=_CONTENT_ALLOWED_TAGS, attributes=_CONTENT_ALLOWED_ATTRIBUTES,
        protocols=_CONTENT_ALLOWED_PROTOCOLS, strip=True,
    )


_FOOTNOTE_DEF_RE = re.compile(r'^\[\^([^\]]+)\]:[ \t]?(.*)$')
_FOOTNOTE_REF_RE = re.compile(r'\[\^([^\]]+)\](?!:)')


def _extract_footnote_defs(body_md):
    """
    Extrait les définitions de notes de bas de page ([^id]: texte, avec ses lignes de
    continuation indentées) de tout le document, où qu'elles soient : la convention
    Quarto/Pandoc les place en fin de document, séparées de leur référence, alors que
    le corps est ensuite découpé en blocs indépendants (_split_content_blocks
    ci-dessous). Renvoie (texte sans les définitions, {id: bloc Markdown de la
    définition}) — chaque segment ne se voit rattacher que les définitions qu'il
    référence réellement (voir _split_content_blocks) : python-markdown rend sinon
    toutes les définitions qu'on lui passe, y compris celles non référencées dans ce
    segment précis, dupliquant leur rendu d'un bloc à l'autre.
    """
    lines = body_md.split("\n")
    remaining = []
    defs = {}
    i = 0
    while i < len(lines):
        match = _FOOTNOTE_DEF_RE.match(lines[i])
        if not match:
            remaining.append(lines[i])
            i += 1
            continue
        def_id = match.group(1)
        def_lines = [lines[i]]
        i += 1
        while i < len(lines) and (not lines[i].strip() or lines[i].startswith((" ", "\t"))):
            if not lines[i].strip() and (i + 1 >= len(lines) or not lines[i + 1].startswith((" ", "\t"))):
                break
            def_lines.append(lines[i])
            i += 1
        defs[def_id] = "\n".join(def_lines)
    return "\n".join(remaining), defs


def _split_content_blocks(body_md):
    """
    Découpe le Markdown d'une cms.ContentPage en blocs "prose"/"callout" pour son
    StreamField body (voir cms.models.ContentPage), en reconnaissant les callouts
    Quarto ci-dessus. Tout le reste (avant/après/entre deux callouts) devient un ou
    plusieurs blocs "prose". Chaque segment est converti indépendamment par
    _content_markdown_to_html puis _restore_wagtail_embeds, comme pour le blog — les
    définitions de notes de bas de page (_extract_footnote_defs) sont rattachées à
    chaque segment avant conversion, python-markdown n'émettant que celles qui y sont
    effectivement référencées.
    """
    body_md = body_md.replace(PAGEBREAK_SHORTCODE, '<hr class="pagebreak">')
    body_md, footnote_defs = _extract_footnote_defs(body_md)
    lines = body_md.split("\n")
    result = []
    prose_lines = []

    def _to_html(markdown_text):
        used_ids = dict.fromkeys(_FOOTNOTE_REF_RE.findall(markdown_text))
        defs_for_segment = "\n\n".join(footnote_defs[i] for i in used_ids if i in footnote_defs)
        text = f"{markdown_text}\n\n{defs_for_segment}" if defs_for_segment else markdown_text
        return _self_close_void_tags(_restore_wagtail_embeds(_content_markdown_to_html(text)))

    def flush_prose():
        text = "\n".join(prose_lines).strip("\n")
        prose_lines.clear()
        if text.strip():
            result.append({"type": "prose", "value": _to_html(text)})

    i = 0
    while i < len(lines):
        match = _CALLOUT_OPEN_RE.match(lines[i])
        if match:
            flush_prose()
            callout_type, title = match.group(1), match.group(2) or ""
            inner_lines = []
            i += 1
            while i < len(lines) and not _FENCE_CLOSE_RE.match(lines[i]):
                inner_lines.append(lines[i])
                i += 1
            i += 1  # saute la ligne de fermeture ":::"
            result.append({
                "type": "callout",
                "value": {"type": callout_type, "title": title, "text": _to_html("\n".join(inner_lines))},
            })
        else:
            prose_lines.append(lines[i])
            i += 1
    flush_prose()
    return result


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


def _collect_image_file(image_id, media_files):
    """Mode zip (export_blog_zip) : au lieu d'une URL vers le site, copie le fichier de
    l'image dans le zip et renvoie un chemin local. Le marqueur wagtail-image:ID (posé à
    côté, pas dans le chemin) suffit à l'import pour reconstruire l'embed quel que soit ce
    chemin — voir _restore_wagtail_embeds, qui ignore complètement l'URL/le chemin."""
    from wagtail.images.models import Image

    try:
        image = Image.objects.get(pk=image_id)
        rendition = image.get_rendition("width-1600")
    except (Image.DoesNotExist, ValueError, TypeError):
        return None
    arcname = f"media/images/{image_id}-{Path(rendition.file.name).name}"
    media_files[arcname] = rendition.file
    return arcname


def _collect_document_file(document_id, media_files):
    from wagtail.documents.models import Document

    try:
        document = Document.objects.get(pk=document_id)
    except (Document.DoesNotExist, ValueError, TypeError):
        return None
    arcname = f"media/documents/{document_id}-{Path(document.file.name).name}"
    media_files[arcname] = document.file
    return arcname


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

    def __init__(self, media_files=None):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.list_stack = []
        self.link_href = None
        self.link_title_marker = None
        # None (défaut) : URL absolues vers le site (export_blogpost_qmd). Un dict : mode
        # zip (export_blog_zip) — les images/documents Wagtail sont copiés dans ce dict
        # (chemin -> fichier) et référencés par un chemin local plutôt qu'une URL.
        self.media_files = media_files

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
                collected = _collect_document_file(link_id, self.media_files) if self.media_files is not None else None
                self.link_href = collected or _resolve_document_url(link_id)
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
            collected = _collect_image_file(attrs["id"], self.media_files) if self.media_files is not None else None
            url = collected or _resolve_image_url(attrs["id"])
            self.out.append(f'![{attrs.get("alt", "")}]({url} "{marker}")\n\n')
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


class _ContentHTMLToMarkdown(_HTMLToMarkdown):
    """
    Étend _HTMLToMarkdown avec les deux structures que produit l'extension "extra" de
    python-markdown mais que BlogPostPage.body ne connaît pas : tableaux et notes de
    bas de page (cms.ContentPage, voir son docstring dans cms/models.py). Capture le
    Markdown d'une cellule de tableau ou d'une définition de note en substituant
    temporairement self.out (_push_capture/_pop_capture) : les gestionnaires hérités
    (gras, liens, images…) fonctionnent alors sans modification à l'intérieur.
    """

    def __init__(self, media_files=None):
        super().__init__(media_files=media_files)
        self._capture_stack = []
        self._table = None
        self._footnotes = None
        self._footnote_ref = None
        self._skip_depth = 0

    def _push_capture(self):
        self._capture_stack.append(self.out)
        self.out = []

    def _pop_capture(self):
        captured = "".join(self.out).strip()
        self.out = self._capture_stack.pop()
        return captured

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self._skip_depth:
            self._skip_depth += 1
            return
        if tag == "table":
            self._table = {"header": [], "rows": [], "in_head": False}
            return
        if self._table is not None:
            if tag == "thead":
                self._table["in_head"] = True
                return
            if tag == "tr":
                self._table["current_row"] = []
                return
            if tag in ("th", "td"):
                self._push_capture()
                return
        if tag == "div" and "footnote" in (attrs.get("class") or "").split():
            self._footnotes = {"items": {}}
            return
        if self._footnotes is not None:
            if tag == "hr":
                return
            if tag == "li":
                self._footnotes["current_id"] = (attrs.get("id") or "").removeprefix("fn:")
                self._push_capture()
                return
            if tag == "a" and "footnote-backref" in (attrs.get("class") or "").split():
                self._skip_depth = 1
                return
        if tag == "sup" and (attrs.get("id") or "").startswith("fnref:"):
            self._footnote_ref = attrs["id"].split(":", 1)[1]
            self._skip_depth = 1
            return
        super().handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if self._skip_depth:
            self._skip_depth -= 1
            if self._skip_depth == 0 and tag == "sup" and self._footnote_ref:
                self.out.append(f"[^{self._footnote_ref}]")
                self._footnote_ref = None
            return
        if self._table is not None:
            if tag == "table":
                self._ensure_blank_line()
                self.out.append(self._render_table(self._table))
                self._table = None
                return
            if tag == "thead":
                self._table["in_head"] = False
                return
            if tag == "tr":
                row = self._table.pop("current_row", [])
                (self._table["header"] if self._table["in_head"] else self._table["rows"]).append(row)
                return
            if tag in ("th", "td"):
                cell = self._pop_capture().replace("|", "\\|").replace("\n", " ")
                self._table["current_row"].append(cell)
                return
        if self._footnotes is not None:
            if tag == "li" and "current_id" in self._footnotes:
                text = self._pop_capture()
                self._footnotes["items"][self._footnotes.pop("current_id")] = text
                return
            if tag == "div" and "current_id" not in self._footnotes:
                self._ensure_blank_line()
                for fn_id, text in self._footnotes["items"].items():
                    self.out.append(f"[^{fn_id}]: {text}\n\n")
                self._footnotes = None
                return
        super().handle_endtag(tag)

    def handle_data(self, data):
        if self._skip_depth:
            return
        super().handle_data(data)

    @staticmethod
    def _render_table(table):
        width = len(table["header"][0]) if table["header"] else (len(table["rows"][0]) if table["rows"] else 0)
        header = table["header"][0] if table["header"] else [""] * width
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(["---"] * width) + " |",
        ]
        for row in table["rows"]:
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines) + "\n\n"


def export_blogpost_qmd(page, media_files=None):
    """
    Sérialise un BlogPostPage (une langue) en texte .qmd. `media_files=None` (défaut,
    utilisé par les boutons individuels et export_blog_qmd) : images/documents Wagtail
    référencés par une URL absolue vers le site. `media_files` un dict : mode zip
    (export_blog_zip) — ils sont copiés dedans (chemin -> fichier) et référencés par un
    chemin local à la place.
    """
    converter = _HTMLToMarkdown(media_files=media_files)
    converter.feed(page.body)

    front = {
        "title": page.title,
        "key": str(page.translation_key),
        "lang": page.locale.language_code,
        "date": page.date.isoformat(),
        "author": page.author.name if page.author_id else "",
        "excerpt": page.excerpt,
        "slug": page.slug,
        "featured": page.featured,
        "tags": list(page.tags.order_by("name").values_list("name", flat=True)),
        "url": page.full_url,
    }
    if page.featured_image_id:
        if media_files is not None:
            front["featured_image"] = _collect_image_file(page.featured_image_id, media_files)
        else:
            front["featured_image"] = _absolute_url(page.featured_image.get_rendition("width-1600").url)

    frontmatter = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return f"---\n{frontmatter}---\n\n{converter.result()}"


def export_blog_zip():
    """
    Zip complet du blog : un .qmd par (article × langue), sous <langue>/<slug>.qmd, plus
    les images et documents Wagtail réellement référencés, sous media/ (dédupliqués par
    identifiant, un même média peut être partagé par plusieurs articles). Les liens vers
    d'autres pages internes (linktype="page") restent des URL absolues vers le site — pas
    de réécriture vers un autre .qmd du zip, même si sa cible s'y trouve aussi.
    """
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        written_media = set()
        seen_slugs = {}
        for page in BlogPostPage.objects.select_related("locale").order_by("locale__language_code", "slug"):
            media_files = {}
            qmd = export_blogpost_qmd(page, media_files=media_files)

            lang = page.locale.language_code
            base_name = page.slug or f"article-{page.pk}"
            count = seen_slugs.get((lang, base_name), 0)
            seen_slugs[(lang, base_name)] = count + 1
            name = base_name if count == 0 else f"{base_name}-{count}"
            zf.writestr(f"{lang}/{name}.qmd", qmd)

            for arcname, file_field in media_files.items():
                if arcname in written_media:
                    continue
                written_media.add(arcname)
                file_field.open("rb")
                try:
                    zf.writestr(arcname, file_field.read())
                finally:
                    file_field.close()
    return buffer.getvalue()


def export_contentpage_qmd(page, media_files=None):
    """
    Sérialise une cms.ContentPage (une langue) en texte .qmd — même contrat
    qu'export_blogpost_qmd (frontmatter key/lang, marqueurs wagtail-image/-document/
    -page), mais parcourt les blocs de body (StreamField) plutôt qu'un RichTextField
    plat : un bloc "prose" devient du Markdown normal, un bloc "callout" devient un div
    Pandoc/Quarto (::: {.callout-...}), voir _ContentHTMLToMarkdown et
    cms.models.ContentPage.
    """
    parts = []
    for block in page.body:
        converter = _ContentHTMLToMarkdown(media_files=media_files)
        if block.block_type == "prose":
            converter.feed(block.value.source)
            parts.append(converter.result())
        elif block.block_type == "callout":
            converter.feed(block.value["text"].source)
            fence_attrs = f'.callout-{block.value["type"]}'
            if block.value["title"]:
                fence_attrs += f' title="{block.value["title"]}"'
            parts.append(f"::: {{{fence_attrs}}}\n{converter.result()}:::\n")
    body_md = "\n".join(parts).strip() + "\n"

    front = {
        "title": page.title,
        "key": str(page.translation_key),
        "lang": page.locale.language_code,
        "pole": page.get_parent().slug,
        "slug": page.slug,
        "url": page.full_url,
    }
    if page.date:
        front["date"] = page.date.isoformat()
    if page.author_id:
        front["author"] = page.author.name
    if page.excerpt:
        front["excerpt"] = page.excerpt
    if page.tags.exists():
        front["tags"] = list(page.tags.order_by("name").values_list("name", flat=True))
    if page.featured_image_id:
        if media_files is not None:
            front["featured_image"] = _collect_image_file(page.featured_image_id, media_files)
        else:
            front["featured_image"] = _absolute_url(page.featured_image.get_rendition("width-1600").url)

    frontmatter = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return f"---\n{frontmatter}---\n\n{body_md}"


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
    author_name = front.get("author") or ""
    if author_name:
        from .models import Author

        page.author = Author.objects.filter(name=author_name, locale=locale).first() or Author.objects.create(
            name=author_name, locale=locale,
        )
    else:
        page.author = None
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


def import_contentpage_qmd(text):
    """
    Crée ou met à jour une cms.ContentPage à partir d'un texte .qmd — même logique
    d'identification (translation_key + lang) qu'import_blogpost_qmd. Le corps est
    reconstruit en blocs "prose"/"callout" par _split_content_blocks. Pour une page
    nouvelle, le frontmatter "pole" (slug de la cms.PolePage parente, tel qu'écrit par
    export_contentpage_qmd) indique où la rattacher ; à défaut, le premier pôle trouvé
    dans la langue cible est utilisé.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("Frontmatter YAML manquant (le fichier doit commencer par ---).")
    front = yaml.safe_load(match.group(1)) or {}
    body_md = match.group(2)

    lang = front.get("lang") or "fr"
    locale = Locale.objects.get(language_code=lang)
    key = front.get("key")

    page = ContentPage.objects.filter(translation_key=key, locale=locale).first() if key else None
    if page is None:
        sibling = (
            ContentPage.objects.filter(translation_key=key).exclude(locale=locale).first() if key else None
        )
        page = sibling.copy_for_translation(locale, copy_parents=True) if sibling else ContentPage(locale=locale)
        if key and not page.pk:
            page.translation_key = key

    page.title = front.get("title") or page.title or front.get("slug") or ""
    page.slug = front.get("slug") or slugify(page.title)
    page.date = _parse_date(front["date"]) if front.get("date") else None
    author_name = front.get("author") or ""
    if author_name:
        from .models import Author

        page.author = Author.objects.filter(name=author_name, locale=locale).first() or Author.objects.create(
            name=author_name, locale=locale,
        )
    else:
        page.author = None
    page.excerpt = (front.get("excerpt") or "")[:300]
    page.body = _split_content_blocks(body_md)

    is_new = page.pk is None
    if is_new:
        poles = PolePage.objects.filter(locale=locale)
        pole_slug = front.get("pole")
        pole = poles.filter(slug=pole_slug).first() if pole_slug else poles.first()
        if pole is None:
            raise ValueError(f"Aucune PolePage en langue « {lang} » pour y rattacher la page.")
        pole.add_child(instance=page)
    page.save_revision().publish()

    tags = front.get("tags") or []
    if tags:
        from core.models import Tag

        page.tags.set([Tag.objects.get_or_create(name=t, defaults={"slug": slugify(t)})[0] for t in tags])

    return page
