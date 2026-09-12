import bleach
import markdown as md
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_ALLOWED_TAGS = [
    "p", "br", "hr", "strong", "em", "b", "i", "u", "s", "del",
    "a", "ul", "ol", "li", "blockquote", "code", "pre",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tr", "th", "td",
    "img", "span",
]
_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title"],
    "*": ["class"],
}
_ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


@register.filter(name="markdown", is_safe=True)
def markdown_filter(text):
    """
    Convertit du Markdown (ou du HTML déjà écrit) en HTML sûr : les liens et la mise en
    forme passent, tout script ou attribut dangereux est retiré. Utile en particulier
    pour les descriptions saisies par les personnes elles-mêmes (fiches de l'annuaire).
    """
    if not text:
        return ""
    html = md.markdown(text, extensions=["extra", "sane_lists"])
    cleaned = bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRIBUTES, protocols=_ALLOWED_PROTOCOLS, strip=True)
    return mark_safe(cleaned)
