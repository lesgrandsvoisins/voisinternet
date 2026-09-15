"""
« Saut de page » du blog (cms.models.BlogPostPage) : réutilise le bouton natif « ligne
horizontale » de l'éditeur riche (aucun JavaScript personnalisé, aucune étape de build),
mais avec sa propre règle de conversion Python pour produire <hr class="pagebreak"/>
plutôt qu'un <hr> nu — afin qu'un simple <hr> venu d'ailleurs (contenu collé, import…)
ne soit jamais confondu avec un saut de page volontaire.
"""
from draftjs_exporter import DOM
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
