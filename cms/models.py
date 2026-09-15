import re

from django.core.paginator import Paginator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page
from wagtail.search import index


class HomePage(Page):
    """Page racine de l'arbre Wagtail (une par site)."""

    intro = RichTextField(blank=True, default="")

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    subpage_types = [
        "cms.StandardPage", "cms.PolePage", "cms.ContactPage", "cms.AssociationPage", "cms.DonationPage",
        "cms.BlogIndexPage",
    ]


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


class BlogIndexPage(Page):
    """Page d'index du blog : liste les BlogPostPage placés dessous, du plus récent au plus ancien."""

    intro = RichTextField(_("introduction"), blank=True, default="")

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    parent_page_types = ["cms.HomePage"]
    subpage_types = ["cms.BlogPostPage"]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        query = request.GET.get("q", "").strip()
        posts = BlogPostPage.objects.live().child_of(self)
        # Recherche plein texte (moteur intégré à Wagtail, base de données — aucune
        # dépendance supplémentaire) plutôt que le tri chronologique habituel.
        posts = posts.search(query) if query else posts.order_by("-date")
        context["posts"] = Paginator(posts, 10).get_page(request.GET.get("page"))
        context["search_query"] = query
        return context


class BlogPostPage(Page):
    """
    Un article de blog : texte enrichi, chapeau, image de une et auteur. La
    date affichée (`date`) est distincte de la date de publication Wagtail —
    elle peut être antérieure, notamment pour les articles repris de l'ancien
    blog Ghost.
    """

    date = models.DateTimeField(_("date de publication"), default=timezone.now)
    author_name = models.CharField(_("auteur"), max_length=140, blank=True, default="")
    excerpt = models.CharField(_("chapeau"), max_length=300, blank=True, default="")
    featured_image = models.ForeignKey(
        "wagtailimages.Image", verbose_name=_("image de une"),
        null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    # "divider" et "pagebreak" (cms/wagtail_hooks.py) : deux boutons distincts, au rendu
    # identique (<hr/>) mais à l'effet différent — seul le second coupe l'article en
    # plusieurs pages (get_context ci-dessous). "hr" (natif) n'est pas utilisé : Draftail
    # n'expose sa ligne horizontale intégrée que comme un commutateur unique, incapable
    # de porter à la fois un simple séparateur et un saut de page.
    body = RichTextField(
        _("texte"), blank=True, default="",
        features=[
            "bold", "italic", "h2", "h3", "h4", "ol", "ul", "link", "document-link", "image", "embed",
            "divider", "pagebreak", "image-gallery",
        ],
    )

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("author_name"),
        FieldPanel("excerpt"),
        FieldPanel("featured_image"),
        FieldPanel(
            "body",
            help_text=_(
                "Le bouton « Saut de page » de la barre d'outils coupe l'article : il se "
                "lit alors en plusieurs pages plutôt qu'en un seul bloc. « Ligne "
                "horizontale » est un simple séparateur visuel, sans effet sur la pagination."
            ),
        ),
    ]

    search_fields = Page.search_fields + [
        index.SearchField("excerpt"),
        index.SearchField("body"),
        index.SearchField("author_name"),
    ]

    parent_page_types = ["cms.BlogIndexPage"]
    subpage_types = []

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        # « Saut de page » : bouton dédié de l'éditeur riche (cms/wagtail_hooks.py), qui
        # coupe l'article en plusieurs pages à l'écran. Toutes les pages sont tout de
        # même transmises au template (body_pages) : à l'impression, l'article s'imprime
        # en entier plutôt qu'une seule page à la fois (core/static/core/css/site.css).
        pages = re.split(r'<hr class="pagebreak"\s*/?>', self.body) if self.body else [""]
        try:
            page_number = int(request.GET.get("page", 1))
        except ValueError:
            page_number = 1
        page_number = max(1, min(page_number, len(pages)))
        context["body_pages"] = pages
        context["body_page"] = pages[page_number - 1]
        context["page_number"] = page_number
        context["total_pages"] = len(pages)
        return context
