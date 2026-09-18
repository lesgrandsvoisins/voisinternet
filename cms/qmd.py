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

Chaque bloc de cms.ContentPage.body porte son propre div Pandoc/Quarto fencé (_fence_div),
jamais un seul div englobant tout le champ : "prose" a donc lui aussi un fence explicite
(::: {.prose}), au lieu d'être le seul bloc sans div — mais l'import reste rétrocompatible
avec un corps sans aucun fence .prose (tout Markdown hors div y est encore traité comme de
la prose implicite, voir _parse_divs/_split_content_blocks).

Un div de classe non reconnue par ailleurs — que la classe soit inconnue, ou que .callout-*/
.pull/.prose contienne lui-même un div imbriqué — devient un cms.GenericBlock/
GenericNestingBlock (cms/models.py) plutôt que d'être perdu : voir _parse_divs (analyse de
l'imbrication par comptage de deux-points, convention Pandoc — un div englobant utilise
strictement plus de deux-points que tout ce qu'il contient, voir
https://quarto.org/docs/authoring/markdown-basics.html#sec-divs-and-spans) et
_nodes_to_blocks (classification en blocs de StreamField) côté import, _export_body_parts
côté export.
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

from .models import BlogIndexPage, BlogPostPage, ContentPage, HomePage, PolePage, ProjectPage, StandardPage

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

# Div Pandoc/Quarto générique : ::: {<attrs>} … ::: — les trois classes reconnues
# ci-dessous gardent leur bloc StreamField dédié (CalloutBlock/PullQuoteBlock/prose
# implicite) ; toute autre classe devient un cms.GenericBlock, ou GenericNestingBlock
# s'il imbrique lui-même d'autres divs (voir _parse_divs ci-dessous). L'imbrication
# suit la convention Pandoc (un div englobant utilise STRICTEMENT plus de deux-points
# que tout ce qu'il contient :
# https://quarto.org/docs/authoring/markdown-basics.html#sec-divs-and-spans) — .callout-
# */.pull/.prose eux-mêmes restent volontairement sans imbrication (voir
# CalloutBlock/PullQuoteBlock, cms/models.py : si l'un d'eux contient malgré tout un
# div imbriqué, _nodes_to_blocks le traite comme un GenericBlock/GenericNestingBlock à
# la place plutôt que de perdre le contenu imbriqué).
_DIV_OPEN_RE = re.compile(r'^(:{3,})\s*\{([^}]*)\}\s*$')
_DIV_CLOSE_RE = re.compile(r'^(:{3,})\s*$')
# Attribut title="…" facultatif, seule forme de titre de callout reconnue (pas de
# première ligne "## Titre" traitée spécialement, pour rester simple).
_CALLOUT_CLASS_RE = re.compile(r'^\.callout-(note|tip|important|warning|caution)(?:\s+title="([^"]*)")?$')
_PULL_CLASS_RE = re.compile(r'^\.pull$')
# ::: {.prose} explicite (voir export_contentpage_qmd/_fence_div) : facultatif à l'import
# — du Markdown hors de tout fence reste traité comme "prose" par _parse_divs (les
# lignes hors div y sont déjà des noeuds "prose"), pour rester compatible avec un .qmd
# écrit à la main sans ce fence ou exporté avant son introduction.
_PROSE_CLASS_RE = re.compile(r'^\.prose$')
# Span Pandoc/Quarto pour une citation en exergue ponctuelle, à l'intérieur d'un
# paragraphe (cms.wagtail_hooks.py::register_pull_feature pour la version Draftail) :
# [texte]{.pull} — avec des accolades comme un attribut de span Pandoc standard, pas
# des parenthèses (qui feraient un lien Markdown normal).
_PULL_SPAN_RE = re.compile(r'\[([^\]]+)\]\{\.pull\}')


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


def _parse_divs(lines, i=0, min_close_colons=0):
    """
    Analyse récursive-descendante d'un corps Markdown en noeuds "prose" (lignes hors de
    tout div) et "div" ({"attrs": <contenu entre {…}>, "children": [noeuds imbriqués]})
    — l'imbrication Pandoc/Quarto se reconnaît par comptage de deux-points (_DIV_OPEN_RE/
    _DIV_CLOSE_RE), pas par un empilement générique de "::: " : un div ne se referme
    que sur une ligne portant au moins autant de deux-points que sa propre ouverture,
    donc jamais sur la fermeture (toujours à colonnes strictement inférieures, par
    convention Pandoc) d'un div qu'il contient. Renvoie (noeuds, index suivant).
    """
    nodes = []
    prose_lines = []

    def flush_prose():
        if prose_lines:
            nodes.append({"type": "prose", "lines": list(prose_lines)})
            prose_lines.clear()

    while i < len(lines):
        line = lines[i]
        close_match = _DIV_CLOSE_RE.match(line)
        if min_close_colons and close_match and len(close_match.group(1)) >= min_close_colons:
            flush_prose()
            return nodes, i + 1  # laisse la ligne de fermeture derrière nous
        open_match = _DIV_OPEN_RE.match(line)
        if open_match:
            flush_prose()
            colons, attrs = len(open_match.group(1)), open_match.group(2).strip()
            children, i = _parse_divs(lines, i + 1, min_close_colons=colons)
            nodes.append({"type": "div", "attrs": attrs, "children": children})
            continue
        prose_lines.append(line)
        i += 1
    flush_prose()
    return nodes, i


# cms.models.ContentStreamBlock n'empile que 3 niveaux concrets de GenericNestingBlock
# (une vraie auto-référence ferait boucler indéfiniment l'outillage de Wagtail qui
# parcourt l'arbre des blocs — voir sa docstring) : au-delà, l'import échoue avec un
# message clair plutôt qu'une erreur Wagtail obscure au moment d'enregistrer la page.
_GENERIC_NESTING_MAX_DEPTH = 3


def _nodes_to_blocks(nodes, to_html, depth=0):
    """
    Convertit les noeuds de _parse_divs en blocs de StreamField ("prose"/"callout"/
    "pull"/"generic"/"generic_nesting", voir cms.models.ContentStreamBlock) : un div de
    classe .callout-*/.pull/.prose garde son bloc dédié tant qu'il ne contient lui-même
    aucun div imbriqué (comme avant — voir CalloutBlock/PullQuoteBlock, cms/models.py) ;
    sinon, ou pour toute autre classe, il devient un GenericBlock (aucun div imbriqué)
    ou un GenericNestingBlock (au moins un), dont les enfants sont convertis
    récursivement — c'est ce qui permet de ne jamais perdre de contenu même dans un
    div imbriqué de classe inconnue. to_html est le convertisseur Markdown->HTML du
    segment appelant (_split_content_blocks), partagé pour que chaque feuille de texte
    profite du même rattachement des notes de bas de page qui la référencent. depth
    compte les GenericNestingBlock déjà traversés, voir _GENERIC_NESTING_MAX_DEPTH.
    """
    result = []
    for node in nodes:
        if node["type"] == "prose":
            html = to_html("\n".join(node["lines"]))
            if html.strip():
                result.append({"type": "prose", "value": html})
            continue

        attrs, children = node["attrs"], node["children"]
        has_nested_div = any(c["type"] == "div" for c in children)

        def prose_html_of(children=children):
            return to_html("\n".join(line for c in children for line in c["lines"]))

        callout_match = None if has_nested_div else _CALLOUT_CLASS_RE.match(attrs)
        pull_match = None if (has_nested_div or callout_match) else _PULL_CLASS_RE.match(attrs)
        prose_match = None if (has_nested_div or callout_match or pull_match) else _PROSE_CLASS_RE.match(attrs)
        if callout_match:
            callout_type, title = callout_match.group(1), callout_match.group(2) or ""
            result.append({"type": "callout", "value": {"type": callout_type, "title": title, "text": prose_html_of()}})
        elif pull_match:
            result.append({"type": "pull", "value": {"text": prose_html_of()}})
        elif prose_match:
            html = prose_html_of()
            if html.strip():
                result.append({"type": "prose", "value": html})
        elif has_nested_div:
            if depth >= _GENERIC_NESTING_MAX_DEPTH:
                raise ValueError(
                    f"Divs génériques imbriqués sur plus de {_GENERIC_NESTING_MAX_DEPTH} "
                    "niveaux (::: {" + attrs + "} …) — non pris en charge."
                )
            result.append({"type": "generic_nesting", "value": {
                "class_name": attrs, "children": _nodes_to_blocks(children, to_html, depth=depth + 1),
            }})
        else:
            result.append({"type": "generic", "value": {"class_name": attrs, "text": prose_html_of()}})
    return result


def _split_content_blocks(body_md):
    """
    Découpe le Markdown d'une cms.ContentPage en blocs de cms.ContentStreamBlock (voir
    _nodes_to_blocks) : callouts, citations en exergue (::: {.pull}), prose explicite
    (::: {.prose}) ou implicite (hors de tout div — voir _PROSE_CLASS_RE), et
    désormais tout div Pandoc/Quarto de classe quelconque, imbriqué ou non
    (GenericBlock/GenericNestingBlock, cms.models.py — voir _parse_divs pour
    l'imbrication). Chaque feuille de texte est convertie indépendamment par
    _content_markdown_to_html puis _restore_wagtail_embeds, comme pour le blog — les
    définitions de notes de bas de page (_extract_footnote_defs) sont rattachées à
    chaque feuille avant conversion, python-markdown n'émettant que celles qui y sont
    effectivement référencées.
    """
    body_md = body_md.replace(PAGEBREAK_SHORTCODE, '<hr class="pagebreak">')
    body_md, footnote_defs = _extract_footnote_defs(body_md)

    def to_html(markdown_text):
        # [texte]{.pull} -> <span class="pull"> directement dans la source Markdown,
        # avant conversion : python-markdown laisse passer le HTML brut inline tel quel.
        markdown_text = _PULL_SPAN_RE.sub(r'<span class="pull">\1</span>', markdown_text)
        used_ids = dict.fromkeys(_FOOTNOTE_REF_RE.findall(markdown_text))
        defs_for_segment = "\n\n".join(footnote_defs[i] for i in used_ids if i in footnote_defs)
        text = f"{markdown_text}\n\n{defs_for_segment}" if defs_for_segment else markdown_text
        return _self_close_void_tags(_restore_wagtail_embeds(_content_markdown_to_html(text)))

    nodes, _ = _parse_divs(body_md.split("\n"))
    return _nodes_to_blocks(nodes, to_html)


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
    (séparateur ou saut de page), <span class="pull"> (citation en exergue, voir
    cms/wagtail_hooks.py::register_pull_feature) -> [texte]{.pull}. Pas une bibliothèque
    HTML→Markdown généraliste : le format d'entrée est entièrement sous notre contrôle
    (cms/models.py:BlogPostPage.body features=). Travaille directement sur le HTML tel
    que stocké en base (pas
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
        # <span class="pull"> (cms/wagtail_hooks.py::register_pull_feature, citation en
        # exergue) -> [texte]{.pull} — une pile plutôt qu'un simple booléen, pour ignorer
        # correctement un <span> sans classe imbriqué à l'intérieur (rare mais possible).
        self._pull_span_stack = []

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
        elif tag == "span":
            is_pull = "pull" in (attrs.get("class") or "").split()
            self._pull_span_stack.append(is_pull)
            if is_pull:
                self.out.append("[")

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
        elif tag == "span" and self._pull_span_stack:
            if self._pull_span_stack.pop():
                self.out.append("]{.pull}")

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
    Étend _HTMLToMarkdown avec ce que BlogPostPage.body ne connaît pas : tableaux et
    notes de bas de page produits par l'extension "extra" de python-markdown
    (cms.ContentPage, voir son docstring dans cms/models.py) — le span <span
    class="pull"> d'une citation en exergue est géré par la classe de base elle-même,
    partagé avec le blog (cms/wagtail_hooks.py::register_pull_feature). Capture le
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


def _export_legacy_meta(front, page):
    """
    Ajoute front["legacy"] = page.legacy_meta si non vide — passe-plat pour les
    métadonnées de frontmatter .qmd d'origine externe (autre outil/pipeline) que ce
    site ne reconnaît pas mais préserve telles quelles à l'aller-retour export/import,
    sans avoir besoin d'en comprendre le contenu (voir cms.models.StandardPage.
    legacy_meta et sa docstring, et _import_legacy_meta pour l'inverse).
    """
    if page.legacy_meta:
        front["legacy"] = page.legacy_meta


def _import_legacy_meta(front):
    """L'inverse de _export_legacy_meta : front.get("legacy") doit être un mapping
    JSON pour être conservé (n'importe quelle autre valeur est ignorée plutôt que de
    faire échouer tout l'import pour un champ qu'on ne fait que transporter)."""
    legacy = front.get("legacy")
    return legacy if isinstance(legacy, dict) else {}


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
    _export_legacy_meta(front, page)

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


# Longueur de fence (nombre de deux-points) par profondeur d'imbrication dans body — même
# convention que workshop/qmd_export/export_transition_qmd.py (voir ses FIELD_COLONS/
# BLOCK_COLONS/ITEM_COLONS/NESTED_ITEM_COLONS) : 6 pour un bloc de premier niveau de body,
# décroissant de 1 à chaque niveau de "generic_nesting" traversé (_export_body_parts), pour
# qu'un div englobant utilise toujours strictement plus de deux-points que tout ce qu'il
# contient (https://quarto.org/docs/authoring/markdown-basics.html#sec-divs-and-spans) — sans
# jamais descendre sous le minimum Pandoc (3, "::: "), puisque ContentStreamBlock (cms/models.py)
# n'empile structurellement que 3 niveaux concrets de GenericNestingBlock (voir
# _GENERIC_NESTING_MAX_DEPTH ci-dessus) : la profondeur maximale possible (3) tombe donc
# exactement sur 6 - 3 = 3, jamais en dessous.
_TOP_LEVEL_COLONS = 6


def _fence_div(fence_attrs, content, colons=_TOP_LEVEL_COLONS):
    """::: {<attrs>}\\n\\n<content>\\n\\n::: — un div Pandoc/Quarto complet par bloc de
    body, jamais un seul div englobant tout le champ (voir export_contentpage_qmd) :
    chaque bloc StreamField porte ainsi sa propre frontière, identifiable par sa classe
    (le block_type, ou une classe plus spécifique — .callout-<type> — quand le bloc a
    lui-même un équivalent Quarto natif plus précis que son seul nom de bloc). colons
    dépend de la profondeur d'imbrication (voir _TOP_LEVEL_COLONS/_export_body_parts)."""
    fence = ":" * colons
    return f"{fence} {{{fence_attrs}}}\n\n{(content or '').strip()}\n\n{fence}\n"


def _export_body_parts(body, media_files=None, depth=0):
    """
    Convertit un StreamValue (cms.ContentPage.body à la racine, depth=0, ou les enfants
    d'un bloc "generic_nesting" à une profondeur croissante — voir
    cms.models.ContentStreamBlock) en une liste de fragments .qmd, un div Pandoc/Quarto
    fencé par bloc (_fence_div, à _TOP_LEVEL_COLONS - depth deux-points) : "prose" devient
    ::: {.prose}, "callout" devient ::: {.callout-...} (classe Quarto native, avec son
    niveau et son titre éventuel), "pull" devient ::: {.pull}, "generic" devient
    ::: {<sa classe d'origine>} et "generic_nesting" de même mais avec ses propres
    enfants exportés récursivement à l'intérieur, à une profondeur (et donc un nombre de
    deux-points) inférieure de un. Un span <span class="pull"> à l'intérieur d'un bloc de
    texte enrichi (cms/wagtail_hooks.py::register_pull_feature) s'exporte en
    [texte]{.pull}, géré par _ContentHTMLToMarkdown elle-même.
    """
    colons = _TOP_LEVEL_COLONS - depth
    parts = []
    for block in body:
        converter = _ContentHTMLToMarkdown(media_files=media_files)
        if block.block_type == "prose":
            converter.feed(block.value.source)
            parts.append(_fence_div(".prose", converter.result(), colons=colons))
        elif block.block_type == "callout":
            converter.feed(block.value["text"].source)
            fence_attrs = f'.callout-{block.value["type"]}'
            if block.value["title"]:
                fence_attrs += f' title="{block.value["title"]}"'
            parts.append(_fence_div(fence_attrs, converter.result(), colons=colons))
        elif block.block_type == "pull":
            converter.feed(block.value["text"].source)
            parts.append(_fence_div(".pull", converter.result(), colons=colons))
        elif block.block_type == "generic":
            converter.feed(block.value["text"].source)
            parts.append(_fence_div(block.value["class_name"], converter.result(), colons=colons))
        elif block.block_type == "generic_nesting":
            inner_parts = _export_body_parts(block.value["children"], media_files=media_files, depth=depth + 1)
            inner_md = "\n".join(inner_parts).strip()
            parts.append(_fence_div(block.value["class_name"], inner_md, colons=colons))
    return parts


def export_contentpage_qmd(page, media_files=None):
    """
    Sérialise une cms.ContentPage (une langue) en texte .qmd — même contrat
    qu'export_blogpost_qmd (frontmatter key/lang, marqueurs wagtail-image/-document/
    -page), mais parcourt les blocs de body (StreamField) plutôt qu'un RichTextField
    plat, via _export_body_parts (voir sa docstring pour la correspondance bloc/div).
    """
    body_md = "\n".join(_export_body_parts(page.body, media_files=media_files)).strip() + "\n"

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
    _export_legacy_meta(front, page)

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
    # [texte]{.pull} -> <span class="pull"> avant markdown_filter, comme pour
    # cms.ContentPage (_split_content_blocks) : le HTML brut inline passe tel quel.
    body_md = _PULL_SPAN_RE.sub(r'<span class="pull">\1</span>', body_md)

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
    page.legacy_meta = _import_legacy_meta(front)

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
    page.legacy_meta = _import_legacy_meta(front)

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


def export_standardpage_qmd(page, media_files=None):
    """
    Sérialise une cms.StandardPage (une langue) en texte .qmd — même schéma
    d'identification (key/lang) que le blog/ContentPage, mais sans leurs champs
    éditoriaux les plus riches (auteur/date/étiquettes) : StandardPage n'a qu'un titre,
    un chapeau (excerpt) et un corps. Depuis cms.0030_standardpage_body_streamfield,
    ce corps est un StreamField (ContentStreamBlock, comme cms.ContentPage) plutôt qu'un simple texte
    enrichi — _export_body_parts reconnaît donc les mêmes divs Pandoc/Quarto
    (callouts, citations en exergue, divs génériques imbriqués sur 3 niveaux) que pour
    ContentPage, au lieu de les laisser fuiter en texte brut dans l'éditeur. "parent"
    (slug de la page parente, quel que soit son type — HomePage/PolePage/StandardPage,
    qui peut s'imbriquer à toute profondeur) indique où la rattacher à l'import si la
    page n'existe pas encore ; voir import_standardpage_qmd pour le repli si absent.
    """
    body_md = "\n".join(_export_body_parts(page.body, media_files=media_files)).strip() + "\n"

    front = {
        "title": page.title,
        "key": str(page.translation_key),
        "lang": page.locale.language_code,
        "parent": page.get_parent().slug,
        "slug": page.slug,
        "url": page.full_url,
    }
    if page.excerpt:
        front["excerpt"] = page.excerpt
    if page.header_image_id:
        if media_files is not None:
            front["header_image"] = _collect_image_file(page.header_image_id, media_files)
        else:
            front["header_image"] = _absolute_url(page.header_image.get_rendition("width-1600").url)
    _export_legacy_meta(front, page)
    frontmatter = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return f"---\n{frontmatter}---\n\n{body_md}"


def import_standardpage_qmd(text):
    """
    Crée ou met à jour une cms.StandardPage à partir d'un texte .qmd — même logique
    d'identification (translation_key + lang) qu'import_blogpost_qmd/
    import_contentpage_qmd, et même reconstruction du corps (StreamField
    ContentStreamBlock) que import_contentpage_qmd::_split_content_blocks. Pour une
    page nouvelle, le frontmatter "parent" (slug de la page parente, tel qu'écrit par
    export_standardpage_qmd) indique où la rattacher ; à défaut, la page d'accueil du
    site (cms.HomePage, seule racine possible dans cet arbre) est utilisée.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("Frontmatter YAML manquant (le fichier doit commencer par ---).")
    front = yaml.safe_load(match.group(1)) or {}
    body_md = match.group(2)

    lang = front.get("lang") or "fr"
    locale = Locale.objects.get(language_code=lang)
    key = front.get("key")

    page = StandardPage.objects.filter(translation_key=key, locale=locale).first() if key else None
    if page is None:
        sibling = (
            StandardPage.objects.filter(translation_key=key).exclude(locale=locale).first() if key else None
        )
        page = sibling.copy_for_translation(locale, copy_parents=True) if sibling else StandardPage(locale=locale)
        if key and not page.pk:
            page.translation_key = key

    page.title = front.get("title") or page.title or front.get("slug") or ""
    page.slug = front.get("slug") or slugify(page.title)
    page.excerpt = (front.get("excerpt") or "")[:300]
    page.body = _split_content_blocks(body_md)
    page.legacy_meta = _import_legacy_meta(front)

    is_new = page.pk is None
    if is_new:
        parent_slug = front.get("parent")
        parent = Page.objects.filter(locale=locale, slug=parent_slug).first() if parent_slug else None
        if parent is None:
            site = Site.objects.filter(is_default_site=True).first()
            parent = site.root_page if site else None
        if parent is None:
            raise ValueError(f"Aucune page parente trouvée en langue « {lang} » pour y rattacher la page.")
        parent.add_child(instance=page)
    page.save_revision().publish()

    return page


# ::: {.cards} : cartes éditoriales (CardBlock, cms.models.py — partagé par plusieurs
# types de page ; seul cms.PolePage.cards est câblé au round-trip .qmd pour l'instant,
# voir export_polepage_qmd/import_polepage_qmd) : un ::: {.card} par carte, avec son
# titre en span Pandoc ([texte]{.title} — CardBlock.title est un CharBlock, pas du
# texte enrichi comme .text, donc pas de div dédié ni de profondeur consommée pour lui)
# et son texte enrichi en div imbriqué ::: {.text}. Même convention de deux-points
# décroissants que _export_body_parts (_TOP_LEVEL_COLONS - depth) : .cards à la
# profondeur 0, .card à 1, .text à 2 — cohérent avec _parse_divs, qui ne dépend que de
# l'ordre (englobant > imbriqué), jamais des valeurs absolues.
_CARDS_CLASS_RE = re.compile(r'^\.cards$')
_CARD_CLASS_RE = re.compile(r'^\.card$')
_CARD_TITLE_SPAN_RE = re.compile(r'^\[(.+)\]\{\.title\}$')
_CARD_TEXT_CLASS_RE = re.compile(r'^\.text$')


def _export_card_content(card_value, media_files, text_colons):
    """Le contenu d'un div ::: {.card} (hors du fence lui-même, laissé à l'appelant —
    cms.PolePage.cards l'imbrique dans ::: {.cards}, cms.ProjectPage.body l'utilise à
    la racine) : titre en span Pandoc, texte enrichi en div ::: {.text} imbriqué à
    text_colons deux-points (un de moins que le fence .card, choisi par l'appelant
    selon sa propre profondeur — voir _fence_div)."""
    converter = _HTMLToMarkdown(media_files=media_files)
    converter.feed(card_value["text"].source)
    text_div = _fence_div(".text", converter.result(), colons=text_colons)
    return f'[{card_value["title"]}]{{.title}}\n\n{text_div}'


def _extract_card_value(card_node, to_html):
    """L'inverse de _export_card_content : reconstruit {"title": …, "text": …} à
    partir des enfants déjà parsés (_parse_divs) d'un div ::: {.card}."""
    title = ""
    text_html = ""
    for child in card_node["children"]:
        if child["type"] == "prose":
            title_match = _CARD_TITLE_SPAN_RE.match("\n".join(child["lines"]).strip())
            if title_match:
                title = title_match.group(1)
        elif child["type"] == "div" and _CARD_TEXT_CLASS_RE.match(child["attrs"]):
            text_html = to_html("\n".join(line for c in child["children"] for line in c["lines"]))
    return {"title": title, "text": text_html}


def _export_cards(cards, media_files=None):
    """Sérialise un StreamField de CardBlock en un div ::: {.cards} (voir les regex
    ci-dessus pour la convention de syntaxe, _import_cards pour l'aller-retour)."""
    card_parts = []
    for block in cards:
        card_content = _export_card_content(block.value, media_files, text_colons=_TOP_LEVEL_COLONS - 2)
        card_parts.append(_fence_div(".card", card_content, colons=_TOP_LEVEL_COLONS - 1))
    cards_md = "\n".join(card_parts).strip()
    return _fence_div(".cards", cards_md, colons=_TOP_LEVEL_COLONS)


def _import_cards(body_md, to_html):
    """Reconstruit une liste de valeurs CardBlock ([{"type": "card", "value": {...}},
    …], prête pour l'affectation à un StreamField) à partir d'un div ::: {.cards} (voir
    _export_cards) — permissif : sans div .cards englobant, chaque ::: {.card} de
    premier niveau du texte est pris en compte directement."""
    nodes, _ = _parse_divs(body_md.split("\n"))
    cards_children = nodes
    for node in nodes:
        if node["type"] == "div" and _CARDS_CLASS_RE.match(node["attrs"]):
            cards_children = node["children"]
            break

    result = []
    for node in cards_children:
        if node["type"] != "div" or not _CARD_CLASS_RE.match(node["attrs"]):
            continue
        result.append({"type": "card", "value": _extract_card_value(node, to_html)})
    return result


def export_polepage_qmd(page, media_files=None):
    """
    Sérialise une cms.PolePage (une langue) en texte .qmd — même schéma
    d'identification (key/lang) que le blog/ContentPage/StandardPage. Couleur, icône,
    étiquette de blog Ghost et étiquettes internes vont en frontmatter (comme
    date/auteur/étiquettes/image de une pour le blog) ; les cartes (cards, voir
    _export_cards) sont le corps. "icon" n'est qu'informatif au réimport, comme
    "featured_image" pour le blog/ContentPage : reconstruire l'image Wagtail
    elle-même n'est pas pris en charge (voir import_polepage_qmd).
    """
    body_md = _export_cards(page.cards, media_files=media_files)
    front = {
        "title": page.title,
        "key": str(page.translation_key),
        "lang": page.locale.language_code,
        "slug": page.slug,
        "lead": page.lead,
        "accent": page.accent,
        "ghost_tag": page.ghost_tag,
        "tags": list(page.tags.order_by("name").values_list("name", flat=True)),
        "url": page.full_url,
    }
    if page.icon_id:
        if media_files is not None:
            front["icon"] = _collect_image_file(page.icon_id, media_files)
        else:
            front["icon"] = _absolute_url(page.icon.get_rendition("width-400").url)
    frontmatter = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return f"---\n{frontmatter}---\n\n{body_md}"


def import_polepage_qmd(text):
    """
    Crée ou met à jour une cms.PolePage à partir d'un texte .qmd — même logique
    d'identification (translation_key + lang) qu'import_blogpost_qmd/
    import_standardpage_qmd. Pour une page nouvelle, le seul parent possible est la
    cms.HomePage de la langue cible (PolePage.parent_page_types), comme la
    BlogIndexPage fixe du blog — pas de champ "parent" à fournir. "icon" du frontmatter
    n'est jamais reconstruit (voir export_polepage_qmd) : image Wagtail à choisir
    depuis l'admin comme avant.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("Frontmatter YAML manquant (le fichier doit commencer par ---).")
    front = yaml.safe_load(match.group(1)) or {}
    body_md = match.group(2)

    lang = front.get("lang") or "fr"
    locale = Locale.objects.get(language_code=lang)
    key = front.get("key")

    page = PolePage.objects.filter(translation_key=key, locale=locale).first() if key else None
    if page is None:
        sibling = (
            PolePage.objects.filter(translation_key=key).exclude(locale=locale).first() if key else None
        )
        page = sibling.copy_for_translation(locale, copy_parents=True) if sibling else PolePage(locale=locale)
        if key and not page.pk:
            page.translation_key = key

    page.title = front.get("title") or page.title or front.get("slug") or ""
    page.slug = front.get("slug") or slugify(page.title)
    page.lead = front.get("lead") or ""
    page.accent = front.get("accent") or "teal"
    page.ghost_tag = front.get("ghost_tag") or ""

    def to_html(markdown_text):
        return _self_close_void_tags(_restore_wagtail_embeds(markdown_filter(markdown_text)))

    page.cards = _import_cards(body_md, to_html)

    is_new = page.pk is None
    if is_new:
        home = HomePage.objects.filter(locale=locale).first()
        if home is None:
            raise ValueError(f"Aucune HomePage en langue « {lang} » pour y rattacher le pôle.")
        home.add_child(instance=page)
    page.save_revision().publish()

    tags = front.get("tags") or []
    if tags:
        from core.models import Tag

        page.tags.set([Tag.objects.get_or_create(name=t, defaults={"slug": slugify(t)})[0] for t in tags])

    return page


# cms.ProjectPage.body mélange 4 types de bloc (card/testimonial/gallery/documents,
# cms/models.py) — chacun devient son propre div de premier niveau (comme "prose"/
# "callout"/"pull" pour cms.ContentPage.body, _export_body_parts), à _TOP_LEVEL_COLONS
# deux-points. .card réutilise _export_card_content/_extract_card_value ci-dessus, à
# une profondeur de un (son propre fence est déjà au niveau racine, colons du .text
# imbriqué = _TOP_LEVEL_COLONS - 1). .testimonial (TestimonialBlock) : auteur·ice en
# span Pandoc ([texte]{.author}, même raison que CardBlock.title — CharBlock, pas de
# texte enrichi), citation en texte brut (TestimonialBlock.quote est un TextBlock —
# affiché tel quel dans le gabarit, jamais passé par |richtext, donc jamais converti
# Markdown<->HTML ici non plus). .gallery (ProjectGalleryBlock) : légende en span
# ([texte]{.caption}), une image par ligne en syntaxe Markdown standard, avec le même
# marqueur wagtail-image:ID que le texte enrichi (_restore_wagtail_embeds) pour
# reconnaître l'image à l'import — sans lui, la ligne est ignorée (image déjà
# supprimée ou ajoutée à la main, non reconstructible). .documents (ListBlock de
# TransparencyDocumentBlock) : une liste à puces, un marqueur wagtail-document:ID par
# lien, ou l'intitulé seul si aucun document n'est encore attaché.
_TESTIMONIAL_CLASS_RE = re.compile(r'^\.testimonial$')
_TESTIMONIAL_AUTHOR_SPAN_RE = re.compile(r'^\[(.+)\]\{\.author\}$')
_GALLERY_CLASS_RE = re.compile(r'^\.gallery$')
_GALLERY_CAPTION_SPAN_RE = re.compile(r'^\[(.+)\]\{\.caption\}$')
_GALLERY_IMAGE_LINE_RE = re.compile(r'^!\[[^\]]*\]\(([^ )]+)(?:\s+"wagtail-image:(\d+)")?\)$')
_DOCUMENTS_CLASS_RE = re.compile(r'^\.documents$')
_DOCUMENT_ITEM_RE = re.compile(r'^-\s+\[(.+)\]\(([^ )]+)(?:\s+"wagtail-document:(\d+)")?\)\s*$')
_DOCUMENT_LABEL_ONLY_RE = re.compile(r'^-\s+(.+)$')


def _export_testimonial(value):
    parts = []
    if value.get("author"):
        parts.append(f'[{value["author"]}]{{.author}}')
    if value.get("quote"):
        parts.append(value["quote"])
    return "\n\n".join(parts)


def _extract_testimonial(node):
    quote_lines = []
    author = ""
    for child in node["children"]:
        if child["type"] != "prose":
            continue
        for line in child["lines"]:
            stripped = line.strip()
            author_match = _TESTIMONIAL_AUTHOR_SPAN_RE.match(stripped)
            if author_match:
                author = author_match.group(1)
            elif stripped:
                quote_lines.append(line)
    return {"quote": "\n".join(quote_lines).strip(), "author": author}


def _export_gallery(value, media_files=None):
    parts = []
    if value.get("caption"):
        parts.append(f'[{value["caption"]}]{{.caption}}')
    lines = []
    for image in value["images"]:
        if media_files is not None:
            url = _collect_image_file(image.pk, media_files) or ""
        else:
            url = _absolute_url(image.get_rendition("width-1600").url)
        lines.append(f'![]({url} "wagtail-image:{image.pk}")')
    if lines:
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _extract_gallery(node):
    caption = ""
    image_ids = []
    for child in node["children"]:
        if child["type"] != "prose":
            continue
        for line in child["lines"]:
            stripped = line.strip()
            if not stripped:
                continue
            caption_match = _GALLERY_CAPTION_SPAN_RE.match(stripped)
            if caption_match:
                caption = caption_match.group(1)
                continue
            image_match = _GALLERY_IMAGE_LINE_RE.match(stripped)
            if image_match and image_match.group(2):
                image_ids.append(int(image_match.group(2)))
    return {"caption": caption, "images": image_ids}


def _export_documents(items, media_files=None):
    lines = []
    for item in items:
        label, document = item["label"], item.get("document")
        if document is None:
            lines.append(f"- {label}")
            continue
        if media_files is not None:
            url = _collect_document_file(document.pk, media_files) or ""
        else:
            url = _absolute_url(document.url)
        lines.append(f'- [{label}]({url} "wagtail-document:{document.pk}")')
    return "\n".join(lines)


def _extract_documents(node):
    result = []
    for child in node["children"]:
        if child["type"] != "prose":
            continue
        for line in child["lines"]:
            stripped = line.strip()
            if not stripped:
                continue
            item_match = _DOCUMENT_ITEM_RE.match(stripped)
            if item_match:
                doc_id = int(item_match.group(3)) if item_match.group(3) else None
                result.append({"label": item_match.group(1), "document": doc_id})
                continue
            label_match = _DOCUMENT_LABEL_ONLY_RE.match(stripped)
            if label_match:
                result.append({"label": label_match.group(1), "document": None})
    return result


def _export_project_body(body, media_files=None):
    """Sérialise cms.ProjectPage.body (voir le commentaire au-dessus des regex pour la
    correspondance bloc/div) — chaque bloc devient son propre div de premier niveau,
    comme _export_body_parts pour cms.ContentPage.body."""
    parts = []
    for block in body:
        if block.block_type == "card":
            content = _export_card_content(block.value, media_files, text_colons=_TOP_LEVEL_COLONS - 1)
            parts.append(_fence_div(".card", content, colons=_TOP_LEVEL_COLONS))
        elif block.block_type == "testimonial":
            parts.append(_fence_div(".testimonial", _export_testimonial(block.value), colons=_TOP_LEVEL_COLONS))
        elif block.block_type == "gallery":
            parts.append(_fence_div(".gallery", _export_gallery(block.value, media_files), colons=_TOP_LEVEL_COLONS))
        elif block.block_type == "documents":
            parts.append(
                _fence_div(".documents", _export_documents(block.value, media_files), colons=_TOP_LEVEL_COLONS)
            )
    return "\n".join(parts).strip() + "\n"


def _import_project_body(body_md, to_html):
    """L'inverse de _export_project_body : reconstruit la liste de blocs
    (prête pour l'affectation à cms.ProjectPage.body) à partir des divs de premier
    niveau du texte .qmd. Un div de classe non reconnue est simplement ignoré (pas de
    GenericBlock ici : contrairement à cms.ContentPage, ProjectPage.body a un jeu de
    blocs fixe, sans équivalent générique)."""
    nodes, _ = _parse_divs(body_md.split("\n"))
    result = []
    for node in nodes:
        if node["type"] != "div":
            continue
        if _CARD_CLASS_RE.match(node["attrs"]):
            result.append({"type": "card", "value": _extract_card_value(node, to_html)})
        elif _TESTIMONIAL_CLASS_RE.match(node["attrs"]):
            result.append({"type": "testimonial", "value": _extract_testimonial(node)})
        elif _GALLERY_CLASS_RE.match(node["attrs"]):
            result.append({"type": "gallery", "value": _extract_gallery(node)})
        elif _DOCUMENTS_CLASS_RE.match(node["attrs"]):
            result.append({"type": "documents", "value": _extract_documents(node)})
    return result


def export_projectpage_qmd(page, media_files=None):
    """
    Sérialise une cms.ProjectPage (une langue) en texte .qmd — même schéma
    d'identification (key/lang) et même convention "pole" (slug de la cms.PolePage
    parente) qu'export_contentpage_qmd, puisque ProjectPage a le même
    parent_page_types. Le corps (body) est sérialisé par _export_project_body.
    """
    body_md = _export_project_body(page.body, media_files=media_files)
    front = {
        "title": page.title,
        "key": str(page.translation_key),
        "lang": page.locale.language_code,
        "pole": page.get_parent().slug,
        "slug": page.slug,
        "lead": page.lead,
        "url": page.full_url,
    }
    if page.date_start:
        front["date_start"] = page.date_start.isoformat()
    if page.date_end:
        front["date_end"] = page.date_end.isoformat()
    if page.location:
        front["location"] = page.location
    if page.tags.exists():
        front["tags"] = list(page.tags.order_by("name").values_list("name", flat=True))
    if page.featured_image_id:
        if media_files is not None:
            front["featured_image"] = _collect_image_file(page.featured_image_id, media_files)
        else:
            front["featured_image"] = _absolute_url(page.featured_image.get_rendition("width-1600").url)

    frontmatter = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return f"---\n{frontmatter}---\n\n{body_md}"


def import_projectpage_qmd(text):
    """
    Crée ou met à jour une cms.ProjectPage à partir d'un texte .qmd — même logique
    d'identification (translation_key + lang) et de rattachement par pôle
    (frontmatter "pole") qu'import_contentpage_qmd.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("Frontmatter YAML manquant (le fichier doit commencer par ---).")
    front = yaml.safe_load(match.group(1)) or {}
    body_md = match.group(2)

    lang = front.get("lang") or "fr"
    locale = Locale.objects.get(language_code=lang)
    key = front.get("key")

    page = ProjectPage.objects.filter(translation_key=key, locale=locale).first() if key else None
    if page is None:
        sibling = (
            ProjectPage.objects.filter(translation_key=key).exclude(locale=locale).first() if key else None
        )
        page = sibling.copy_for_translation(locale, copy_parents=True) if sibling else ProjectPage(locale=locale)
        if key and not page.pk:
            page.translation_key = key

    page.title = front.get("title") or page.title or front.get("slug") or ""
    page.slug = front.get("slug") or slugify(page.title)
    page.lead = front.get("lead") or ""
    page.date_start = _parse_date(front["date_start"]) if front.get("date_start") else None
    page.date_end = _parse_date(front["date_end"]) if front.get("date_end") else None
    page.location = front.get("location") or ""

    def to_html(markdown_text):
        return _self_close_void_tags(_restore_wagtail_embeds(markdown_filter(markdown_text)))

    page.body = _import_project_body(body_md, to_html)

    is_new = page.pk is None
    if is_new:
        poles = PolePage.objects.filter(locale=locale)
        pole_slug = front.get("pole")
        pole = poles.filter(slug=pole_slug).first() if pole_slug else poles.first()
        if pole is None:
            raise ValueError(f"Aucune PolePage en langue « {lang} » pour y rattacher le projet.")
        pole.add_child(instance=page)
    page.save_revision().publish()

    tags = front.get("tags") or []
    if tags:
        from core.models import Tag

        page.tags.set([Tag.objects.get_or_create(name=t, defaults={"slug": slugify(t)})[0] for t in tags])

    return page
