from django import template

from core import evenements

register = template.Library()


@register.filter
def plage_texte(event):
    return evenements.plage_texte(event)


@register.simple_tag
def pastille_dates(event):
    return evenements.plage_pastille(event)
