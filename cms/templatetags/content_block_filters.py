"""
Affichage générique de cms.GenericBlock/GenericNestingBlock (cms/templates/cms/
partials/content_blocks.html) : la classe brute d'un div Pandoc/Quarto de classe non
reconnue (ex. ".sidebar", "#special .sidebar", ou même une classe avec des
attributs key="valeur") est stockée telle quelle (voir cms/qmd.py::_parse_divs) —
pandoc_classes n'en retient que les tokens ".classe" pour un rendu CSS minimal ;
identifiants et attributs key="valeur" ne sont pas repris.
"""
import re

from django import template

register = template.Library()

_CLASS_TOKEN_RE = re.compile(r'\.(-?[A-Za-z_][\w-]*)')


@register.filter
def pandoc_classes(attrs):
    if not attrs:
        return ""
    return " ".join(_CLASS_TOKEN_RE.findall(attrs))
