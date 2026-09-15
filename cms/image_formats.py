"""
Tailles supplémentaires pour les images insérées en texte enrichi, en plus des formats
natifs de Wagtail (Pleine largeur, Aligné à gauche, Aligné à droite) : voir
wagtail.images.formats et core/static/core/css/site.css pour le rendu (classes
richtext-image small/medium/large).
"""
from django.utils.translation import gettext_lazy as _

from wagtail.images.formats import Format, register_image_format

register_image_format(Format("small", _("Petite"), "richtext-image small", "width-400"))
register_image_format(Format("medium", _("Moyenne"), "richtext-image medium", "width-700"))
register_image_format(Format("large", _("Grande"), "richtext-image large", "width-1000"))
