"""
Tailles supplémentaires pour les images insérées en texte enrichi, en plus des formats
natifs de Wagtail (Pleine largeur, Aligné à gauche, Aligné à droite) : voir
wagtail.images.formats et core/static/core/css/site.css pour le rendu.

La taille (petite/moyenne/grande) est indépendante de l'alignement : chaque taille existe
seule (centrée, comme une image normale) et combinée à gauche/droite. Le format natif
Wagtail ne propose qu'une seule liste à plat (pas deux axes indépendants) : on
recense donc ici toutes les combinaisons utiles plutôt que de dupliquer l'alignement.
« Pleine largeur » reste seule, sans variante de taille — une pleine largeur réduite n'a
pas vraiment de sens.

Chaque classe CSS ci-dessous (small/medium/large, left/right) existe déjà indépendamment
dans core/static/core/css/site.css : les combiner dans une seule chaîne de `classname`
suffit à cumuler les deux effets, sans CSS supplémentaire à écrire.
"""
from django.utils.translation import gettext_lazy as _

from wagtail.images.formats import Format, register_image_format

register_image_format(Format("small", _("Petite"), "richtext-image small", "width-400"))
register_image_format(Format("medium", _("Moyenne"), "richtext-image medium", "width-700"))
register_image_format(Format("large", _("Grande"), "richtext-image large", "width-1000"))

register_image_format(
    Format("left-small", _("Petite, à gauche"), "richtext-image left small", "width-400")
)
register_image_format(
    Format("left-medium", _("Moyenne, à gauche"), "richtext-image left medium", "width-700")
)
register_image_format(
    Format("left-large", _("Grande, à gauche"), "richtext-image left large", "width-1000")
)
register_image_format(
    Format("right-small", _("Petite, à droite"), "richtext-image right small", "width-400")
)
register_image_format(
    Format("right-medium", _("Moyenne, à droite"), "richtext-image right medium", "width-700")
)
register_image_format(
    Format("right-large", _("Grande, à droite"), "richtext-image right large", "width-1000")
)
