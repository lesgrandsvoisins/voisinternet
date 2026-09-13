from django.db import models
from django.utils.translation import gettext_lazy as _

from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page


class HomePage(Page):
    """Page racine de l'arbre Wagtail (une par site)."""

    intro = RichTextField(blank=True, default="")

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    subpage_types = ["cms.StandardPage", "cms.PolePage", "cms.ContactPage", "cms.AssociationPage", "cms.DonationPage"]


class StandardPage(Page):
    """Page de contenu générique : un titre et un corps en texte enrichi."""

    body = RichTextField(blank=True, default="")

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]

    parent_page_types = ["cms.HomePage", "cms.StandardPage", "cms.PolePage"]
    subpage_types = ["cms.StandardPage"]

    def get_pole_ancestor(self):
        """Le PolePage ancêtre le plus proche, le cas échéant (couleur/icône à reprendre dans le fil d'Ariane)."""
        ancestor = self.get_ancestors().type(PolePage).order_by("-depth").first()
        return ancestor.specific if ancestor else None


class CardBlock(blocks.StructBlock):
    """Une carte éditoriale (titre + texte enrichi) : réutilisée par plusieurs types de page."""

    title = blocks.CharBlock(label=_("titre"))
    text = blocks.RichTextBlock(label=_("texte"))

    class Meta:
        icon = "doc-full"
        label = _("carte")


class BoardMemberBlock(blocks.StructBlock):
    name = blocks.CharBlock(label=_("nom"))
    role = blocks.CharBlock(label=_("rôle"))

    class Meta:
        icon = "user"
        label = _("membre du bureau")


class TransparencyDocumentBlock(blocks.StructBlock):
    label = blocks.CharBlock(label=_("intitulé"))
    document = DocumentChooserBlock(label=_("document"), required=False)

    class Meta:
        icon = "doc-full-inverse"
        label = _("document")


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
    cards = StreamField([("card", CardBlock())], blank=True)

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


class ContactPage(Page):
    """Page de contact : un chapeau et des cartes éditoriales (courriel, agenda…)."""

    lead = models.CharField(_("chapeau"), max_length=240, blank=True, default="")
    cards = StreamField([("card", CardBlock())], blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("lead"),
        FieldPanel("cards"),
    ]

    parent_page_types = ["cms.HomePage"]
    subpage_types = []


class AssociationPage(Page):
    """
    Page de présentation de l'association (raison d'être, bureau, statut
    légal, transparence…). Les sections sont libres : cartes de texte,
    liste du bureau, liste de documents à télécharger.
    """

    lead = models.CharField(_("chapeau"), max_length=240, blank=True, default="")
    body = StreamField(
        [
            ("card", CardBlock()),
            ("board", blocks.ListBlock(BoardMemberBlock(), label=_("bureau"))),
            ("documents", blocks.ListBlock(TransparencyDocumentBlock(), label=_("documents"))),
        ],
        blank=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("lead"),
        FieldPanel("body"),
    ]

    parent_page_types = ["cms.HomePage"]
    subpage_types = []


class DonationPage(Page):
    """
    Page « Dons » : des cartes éditoriales, plus deux sections toujours à
    jour car tirées des données de l'association plutôt que du contenu
    éditorial — les moyens de don actifs (core.Service) et les soutiens
    publics (core.Donor).
    """

    lead = models.CharField(_("chapeau"), max_length=240, blank=True, default="")
    cards = StreamField([("card", CardBlock())], blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("lead"),
        FieldPanel("cards"),
    ]

    parent_page_types = ["cms.HomePage"]
    subpage_types = []

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        from core.models import Donor, Service

        context["donation_services"] = Service.objects.filter(
            slug__in=["helloasso", "paypal", "stripe"], active=True,
        ).order_by("order", "name")
        context["donors"] = Donor.objects.filter(public=True)
        return context
