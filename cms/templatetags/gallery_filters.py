"""Deux filtres appliqués au texte enrichi d'un article de blog après conversion en HTML
final (embeds Wagtail déjà résolus en <img>) : `gallery_grid` regroupe les images
consécutives dans un <div class="gallery">, `image_captions` affiche le texte
alternatif de chaque image comme légende dessous.

Deux formes à reconnaître pour une galerie, selon l'origine du contenu :
- éditeur natif (bouton « Image » ou « Galerie de photos », cms/wagtail_hooks.py) :
  des <img> qui se suivent, séparés par un <p> vide — artefact de Draft.js (chaque bloc
  atomique est encadré de paragraphes vides pour pouvoir y placer le curseur) ;
- import Ghost (converti depuis du Markdown) : des <p><img></p> qui se suivent sans écart.

Une image isolée n'est jamais concernée par le regroupement en galerie : il en faut au
moins deux à la suite.
"""
import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

_IMG = r"<img\b[^>]*>"
_EMPTY_P = r"<p[^>]*>\s*</p>"
_GHOST_IMG_P = r"<p[^>]*>\s*" + _IMG + r"\s*</p>"

_NATIVE_RUN = re.compile(
    r"(?:" + _EMPTY_P + r")?(?:" + _IMG + r"(?:" + _EMPTY_P + _IMG + r")+)(?:" + _EMPTY_P + r")?"
)
_GHOST_RUN = re.compile(r"(?:" + _GHOST_IMG_P + r"){2,}")


def _wrap(match):
    imgs = re.findall(_IMG, match.group(0))
    return '<div class="gallery">' + "".join(imgs) + "</div>"


@register.filter
def gallery_grid(html):
    if not html:
        return html
    html = _NATIVE_RUN.sub(_wrap, html)
    html = _GHOST_RUN.sub(_wrap, html)
    return mark_safe(html)


def _attr(tag, name):
    m = re.search(name + r'="([^"]*)"', tag)
    return m.group(1) if m else ""


_SOLO_GHOST_IMG_P = re.compile(r"<p[^>]*>\s*(" + _IMG + r")\s*</p>")


def _captionize(img_tag):
    classes = _attr(img_tag, "class").split()
    # Une image alignée à gauche/droite (flotte dans le texte) n'est pas légendée : une
    # <figcaption> casserait la mise en page du flottant (core/static/core/css/site.css,
    # img.left/img.right). Seules les images centrées ou en galerie le sont.
    if "left" in classes or "right" in classes:
        return img_tag
    alt = _attr(img_tag, "alt")
    size = next((c for c in classes if c in ("small", "medium", "large")), None)
    figure_class = "img-figure " + size if size else "img-figure"
    caption = f"<figcaption>{escape(alt)}</figcaption>" if alt else ""
    return f'<figure class="{figure_class}">{img_tag}{caption}</figure>'


@register.filter
def image_captions(html):
    if not html:
        return html
    # <p> qui n'enveloppe qu'une image isolée (import Ghost, pas une galerie — déjà
    # traitée par gallery_grid) : on retire le <p>, une <figure> ne peut pas s'y imbriquer.
    html = _SOLO_GHOST_IMG_P.sub(lambda m: m.group(1), html)
    # Toutes les images restantes (isolées, ou dans une galerie) deviennent une <figure>,
    # avec sa légende (texte alternatif) si elle en a une.
    html = re.sub(_IMG, lambda m: _captionize(m.group(0)), html)
    return mark_safe(html)
