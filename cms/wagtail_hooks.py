"""
« Ligne horizontale » et « Saut de page » du blog (cms.models.BlogPostPage) : deux
boutons distincts dans l'éditeur riche, au rendu identique (<hr/>) mais à l'effet
différent — seul le second coupe l'article en plusieurs pages (BlogPostPage.get_context).
Draftail n'expose sa ligne horizontale intégrée que comme un commutateur unique
(`enableHorizontalRule`) : impossible d'en avoir deux variantes par ce biais, d'où ces
deux entités personnalisées (même schéma que « Galerie de photos » ci-dessous), qui
s'insèrent directement au clic plutôt que d'ouvrir une fenêtre de choix.
"""
from draftjs_exporter import DOM
from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.rich_text.converters.contentstate_models import Entity
from wagtail.admin.rich_text.converters.html_to_contentstate import AtomicBlockEntityElementHandler
from wagtail.admin.rich_text.editors.draftail import features as draftail_features


class DividerHandler(AtomicBlockEntityElementHandler):
    def create_entity(self, name, attrs, state, contentstate):
        return Entity("DIVIDER", "IMMUTABLE", {})


class PageBreakHandler(AtomicBlockEntityElementHandler):
    def create_entity(self, name, attrs, state, contentstate):
        return Entity("PAGE_BREAK", "IMMUTABLE", {})


@hooks.register("register_rich_text_features")
def register_divider_feature(features):
    features.register_editor_plugin(
        "draftail",
        "divider",
        draftail_features.EntityFeature(
            {"type": "DIVIDER", "icon": "minus", "description": _("Ligne horizontale")},
            js=["cms/js/draftail_hr.js"],
        ),
    )
    features.register_converter_rule(
        "contentstate",
        "divider",
        {
            # Priorité plus basse que 'hr[class="pagebreak"]' (html_ruleset.py) : un
            # <hr class="pagebreak"> tombe dans PageBreakHandler ci-dessous, tout le
            # reste (y compris un <hr> nu venu d'ailleurs — contenu collé, import…) ici.
            "from_database_format": {"hr": DividerHandler()},
            "to_database_format": {
                "entity_decorators": {"DIVIDER": lambda props: DOM.create_element("hr")},
            },
        },
    )


@hooks.register("register_rich_text_features")
def register_pagebreak_feature(features):
    features.register_editor_plugin(
        "draftail",
        "pagebreak",
        draftail_features.EntityFeature(
            {"type": "PAGE_BREAK", "icon": "doc-empty", "description": _("Saut de page")},
            js=["cms/js/draftail_hr.js"],
        ),
    )
    features.register_converter_rule(
        "contentstate",
        "pagebreak",
        {
            "from_database_format": {'hr[class="pagebreak"]': PageBreakHandler()},
            "to_database_format": {
                "entity_decorators": {
                    "PAGE_BREAK": lambda props: DOM.create_element("hr", {"class": "pagebreak"}),
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


@hooks.register("insert_editor_js")
def insert_image_default_format_js():
    """
    Présélectionne « Pleine largeur » à l'insertion d'une image en texte enrichi (bouton
    natif ou « Galerie de photos » ci-dessus) : voir draftail_image_defaults.js. Un hook
    d'éditeur plutôt qu'un `js=[...]` de fonctionnalité, pour s'appliquer à tous les
    champs de texte enrichi du site, pas seulement ceux qui déclarent "image-gallery".
    """
    return format_html('<script src="{}"></script>', static("cms/js/draftail_image_defaults.js"))


@hooks.register("insert_global_admin_css")
def insert_divider_pagebreak_css():
    """Distingue visuellement les deux <hr/> de draftail_hr.js dans l'éditeur (ligne
    pleine contre pointillée, avec repère « Saut de page ») — les deux boutons ci-dessus
    produisent sinon un <hr/> identique à l'écran tant qu'on n'a pas cliqué dessus. Pas de
    hook "par éditeur" pour du CSS (seulement insert_editor_js) : celui-ci s'applique à
    tout l'admin, sans risque puisque la classe visée n'apparaît que dans ce contexte."""
    return format_html('<link rel="stylesheet" href="{}">', static("cms/css/draftail_hr.css"))
