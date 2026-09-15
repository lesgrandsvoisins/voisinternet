"""Regroupe les images consécutives d'un article de blog dans un <div class="gallery">,
une fois le texte enrichi converti en HTML final (embeds Wagtail déjà résolus en <img>).

Deux formes à reconnaître, selon l'origine du contenu :
- éditeur natif (bouton « Image » ou « Galerie de photos », cms/wagtail_hooks.py) :
  des <img> qui se suivent, séparés par un <p> vide — artefact de Draft.js (chaque bloc
  atomique est encadré de paragraphes vides pour pouvoir y placer le curseur) ;
- import Ghost (converti depuis du Markdown) : des <p><img></p> qui se suivent sans écart.

Une image isolée n'est jamais concernée : il en faut au moins deux à la suite.
"""
import re

from django import template
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
