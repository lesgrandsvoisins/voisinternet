from django.db import models
from django.utils.translation import gettext_lazy as _

from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page


class HomePage(Page):
    """Page racine de l'arbre Wagtail (une par site)."""

    intro = RichTextField(blank=True, default="")

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    subpage_types = ["cms.StandardPage", "cms.PolePage"]


class StandardPage(Page):
    """Page de contenu générique : un titre et un corps en texte enrichi."""

    body = RichTextField(blank=True, default="")

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]

    parent_page_types = ["cms.HomePage", "cms.StandardPage", "cms.PolePage"]
    subpage_types = ["cms.StandardPage"]


class PoleCardBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("titre"))
    text = blocks.RichTextBlock(label=_("texte"))

    class Meta:
        icon = "doc-full"
        label = _("carte")


class PolePage(Page):
    """
    Une page de pôle (civisme, arts plastiques, numérique…) : un chapeau, des
    cartes éditoriales, et les derniers articles du blog portant une étiquette
    donnée. Une couleur (et une icône facultative) distingue chaque pôle.
    """

    ACCENT_CHOICES = [
        ("terracotta", _("Terracotta")),
        ("plum", _("Prune")),
        ("indigo", _("Indigo")),
        ("teal", _("Sarcelle")),
        ("moss", _("Mousse")),
        ("gold", _("Or")),
    ]

    lead = models.CharField(_("chapeau"), max_length=240, blank=True, default="")
    accent = models.CharField(_("couleur du pôle"), max_length=20, choices=ACCENT_CHOICES, default="teal")
    icon = models.ForeignKey(
        "wagtailimages.Image", verbose_name=_("icône du pôle"),
        null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    ghost_tag = models.CharField(
        _("étiquette du blog"), max_length=100, blank=True, default="",
        help_text=_("Étiquette Ghost dont les derniers articles apparaissent en bas de page."),
    )
    cards = StreamField([("card", PoleCardBlock())], blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("lead"),
        FieldPanel("accent"),
        FieldPanel("icon"),
        FieldPanel("ghost_tag"),
        FieldPanel("cards"),
    ]

    parent_page_types = ["cms.HomePage"]
    subpage_types = ["cms.StandardPage"]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        from core.ghost import posts_by_tag

        context["posts"] = posts_by_tag(self.ghost_tag) if self.ghost_tag else []
        return context
