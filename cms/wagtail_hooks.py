"""
« Saut de page » du blog (cms.models.BlogPostPage) : réutilise le bouton natif « ligne
horizontale » de l'éditeur riche (aucun JavaScript personnalisé, aucune étape de build),
mais avec sa propre règle de conversion Python pour produire <hr class="pagebreak"/>
plutôt qu'un <hr> nu — afin qu'un simple <hr> venu d'ailleurs (contenu collé, import…)
ne soit jamais confondu avec un saut de page volontaire.
"""
from draftjs_exporter import DOM
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.rich_text.converters.html_to_contentstate import HorizontalRuleHandler
from wagtail.admin.rich_text.editors.draftail import features as draftail_features


@hooks.register("register_rich_text_features")
def register_pagebreak_feature(features):
    features.register_editor_plugin(
        "draftail", "pagebreak", draftail_features.BooleanFeature("enableHorizontalRule"),
    )
    features.register_converter_rule(
        "contentstate",
        "pagebreak",
        {
            "from_database_format": {
                "hr": HorizontalRuleHandler(),
            },
            "to_database_format": {
                "entity_decorators": {
                    "HORIZONTAL_RULE": lambda props: DOM.create_element("hr", {"class": "pagebreak"}),
                },
            },
        },
    )


@hooks.register("register_rich_text_features")
def register_image_gallery_feature(features):
    """
    Bouton « Galerie de photos » : ouvre le sélecteur d'image natif comme le bouton
    « Image » normal, mais le rouvre automatiquement après chaque choix au lieu de se
    refermer, jusqu'à ce qu'on ferme la fenêtre — pour ajouter plusieurs photos à la
    suite sans rouvrir le bouton à chaque fois. Les images créées sont des entités
    IMAGE tout à fait normales (mêmes règles de conversion que le bouton natif, ci-
    dessous rien à ajouter) : la mise en page en grille vient de core/static/core/css/
    site.css, qui détecte plusieurs images consécutives.
    """
    features.register_editor_plugin(
        "draftail",
        "image-gallery",
        draftail_features.EntityFeature(
            {
                "type": "IMAGE_GALLERY",
                "icon": "image",
                "description": _("Galerie de photos"),
                "chooserUrls": {
                    "imageChooser": reverse_lazy("wagtailimages_chooser:choose"),
                },
            },
            js=["cms/js/draftail_gallery.js"],
        ),
    )
