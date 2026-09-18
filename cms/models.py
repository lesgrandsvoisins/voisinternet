import re
from html import unescape

from django.core.paginator import Paginator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.fields import RichTextField, StreamField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.models import Locale, Page, TranslatableMixin
from wagtail.search import index
from wagtail.snippets.models import register_snippet


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


class TestimonialBlock(blocks.StructBlock):
    """Un témoignage (cms.ProjectPage) : une citation et qui l'a dite."""

    quote = blocks.TextBlock(label=_("citation"))
    author = blocks.CharBlock(label=_("auteur·rice"), required=False)

    class Meta:
        icon = "openquote"
        label = _("témoignage")


class ProjectGalleryBlock(blocks.StructBlock):
    """Une galerie de photos (cms.ProjectPage), affichée en grille — même principe que
    core/static/core/css/site.css pour le blog, mais construite explicitement ici
    plutôt que détectée dans du texte enrichi."""

    caption = blocks.CharBlock(label=_("légende"), required=False)
    images = blocks.ListBlock(ImageChooserBlock(), label=_("photos"))

    class Meta:
        icon = "image"
        label = _("galerie")


CONTENT_RICHTEXT_FEATURES = [
    "bold", "italic", "h2", "h3", "h4", "ol", "ul", "link", "document-link", "image", "embed",
    "divider", "pagebreak", "image-gallery",
]


class CalloutBlock(blocks.StructBlock):
    """
    Un encart (::: {.callout-...} en Quarto) : type, titre facultatif, texte enrichi
    pouvant porter plusieurs paragraphes — un StructBlock plutôt qu'une entité Draftail,
    pour rester isomorphe avec un callout Quarto de plusieurs paragraphes/listes (voir
    cms/qmd.py). Les cinq types correspondent aux callouts natifs de Quarto.
    """

    CALLOUT_CHOICES = [
        ("note", _("Note")),
        ("tip", _("Astuce")),
        ("important", _("Important")),
        ("warning", _("Avertissement")),
        ("caution", _("Attention")),
    ]

    type = blocks.ChoiceBlock(choices=CALLOUT_CHOICES, default="note", label=_("type"))
    title = blocks.CharBlock(label=_("titre"), required=False)
    text = blocks.RichTextBlock(label=_("texte"), features=CONTENT_RICHTEXT_FEATURES)

    class Meta:
        icon = "help"
        label = _("encart")


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
    # Étiquettes internes (core.Tag, partagées avec l'annuaire, les services et le blog
    # interne) : distinct de ghost_tag ci-dessus, qui ne concerne que l'ancien blog Ghost.
    tags = models.ManyToManyField("core.Tag", blank=True, related_name="poles", verbose_name=_("étiquettes"))
    cards = StreamField([("card", CardBlock())], blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("lead"),
        FieldPanel("accent"),
        FieldPanel("icon"),
        FieldPanel("ghost_tag"),
        FieldPanel("tags"),
        FieldPanel("cards"),
    ]

    parent_page_types = ["cms.HomePage"]
    subpage_types = ["cms.StandardPage", "cms.ProjectPage", "cms.ContentPage"]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        from django.utils import timezone

        from core.ghost import posts_by_tag
        from core.models import DirectoryEntry, Event

        context["posts"] = posts_by_tag(self.ghost_tag) if self.ghost_tag else []
        context["projects"] = ProjectPage.objects.live().child_of(self).order_by("-date_start")
        # Cartes = sous-pages ContentPage publiées, dans l'ordre de l'arbre Wagtail
        # (glisser-déposer dans l'admin) — voir cms/templates/cms/pole_page.html.
        context["content_cards"] = ContentPage.objects.live().child_of(self).order_by("path")
        # Articles du blog interne, fiches de l'annuaire et évènements de l'agenda
        # partageant une étiquette (core.Tag) avec ce pôle — vide si le pôle n'a
        # lui-même aucune étiquette (voir gabarit : chaque section reste masquée si vide).
        pole_tag_ids = list(self.tags.values_list("pk", flat=True))
        context["pole_posts"] = (
            BlogPostPage.objects.live().filter(tags__in=pole_tag_ids).distinct().order_by("-date")[:6]
            if pole_tag_ids else BlogPostPage.objects.none()
        )
        context["pole_entries"] = (
            DirectoryEntry.objects.filter(
                tags__in=pole_tag_ids, visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=True,
            ).distinct().order_by("name")[:6]
            if pole_tag_ids else DirectoryEntry.objects.none()
        )
        context["pole_events"] = (
            Event.objects.filter(tags__in=pole_tag_ids, public=True, start__gte=timezone.now())
            .distinct().order_by("start")[:6]
            if pole_tag_ids else Event.objects.none()
        )
        return context


class ProjectPage(Page):
    """
    Un évènement ou projet marquant, présenté en détail sous un pôle (galerie, lieu,
    témoignages…) — plus riche qu'une simple entrée d'agenda (core.Event), pour les
    réalisations qui méritent leur propre page (ex. la Profession d'Empathie Nationale).
    """

    lead = models.CharField(_("chapeau"), max_length=240, blank=True, default="")
    date_start = models.DateField(_("date de début"), null=True, blank=True)
    date_end = models.DateField(_("date de fin"), null=True, blank=True)
    location = models.CharField(_("lieu"), max_length=200, blank=True, default="")
    featured_image = models.ForeignKey(
        "wagtailimages.Image", verbose_name=_("image de une"),
        null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    tags = models.ManyToManyField("core.Tag", blank=True, related_name="projects", verbose_name=_("étiquettes"))
    body = StreamField(
        [
            ("card", CardBlock()),
            ("testimonial", TestimonialBlock()),
            ("gallery", ProjectGalleryBlock()),
            ("documents", blocks.ListBlock(TransparencyDocumentBlock(), label=_("documents"))),
        ],
        blank=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("lead"),
        FieldPanel("date_start"),
        FieldPanel("date_end"),
        FieldPanel("location"),
        FieldPanel("featured_image"),
        FieldPanel("tags"),
        FieldPanel("body"),
    ]

    search_fields = Page.search_fields + [
        index.SearchField("lead"),
        index.SearchField("location"),
    ]

    parent_page_types = ["cms.PolePage"]
    subpage_types = []


_HEADING_RE = re.compile(r'<(h[234])>(.*?)</\1>', re.S)
_TAG_RE = re.compile(r'<[^>]+>')


def _add_heading_anchors(html, seen_slugs):
    """
    Ajoute un id= à chaque titre (h2/h3/h4) d'un fragment HTML de cms.ContentPage, pour
    que le sommaire (ContentPage.get_context) puisse y créer des ancres. seen_slugs,
    partagé entre tous les fragments d'une même page, évite les doublons entre deux
    titres au même texte. Renvoie (html annoté, [(niveau, texte, ancre), ...]).
    """
    entries = []

    def _replace(match):
        level, inner = match.group(1), match.group(2)
        text = _TAG_RE.sub("", inner).strip()
        slug = slugify(text) or "section"
        count = seen_slugs.get(slug, 0)
        seen_slugs[slug] = count + 1
        if count:
            slug = f"{slug}-{count}"
        entries.append((level, text, slug))
        return f'<{level} id="{slug}">{inner}</{level}>'

    return _HEADING_RE.sub(_replace, html), entries


class ContentPage(Page):
    """
    Une page de contenu isomorphe avec Quarto (.qmd) : sous-page d'un pôle, dont les
    instances publiées apparaissent comme des cartes sur la page de leur pôle (voir
    PolePage.get_context et cms/templates/cms/pole_page.html). Calquée sur
    BlogPostPage, mais body est un StreamField plutôt qu'un simple RichTextField : un
    callout Quarto peut porter plusieurs paragraphes, ce qu'une seule entité de texte
    enrichi ne peut pas représenter fidèlement (voir cms/qmd.py pour l'aller-retour
    avec le fichier .qmd).
    """

    date = models.DateTimeField(_("date de publication"), null=True, blank=True)
    author = models.ForeignKey(
        "cms.Author", verbose_name=_("auteur·ice"),
        null=True, blank=True, on_delete=models.SET_NULL, related_name="content_pages",
    )
    excerpt = models.CharField(_("chapeau"), max_length=300, blank=True, default="")
    featured_image = models.ForeignKey(
        "wagtailimages.Image", verbose_name=_("image de une"),
        null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    tags = models.ManyToManyField("core.Tag", blank=True, related_name="content_pages", verbose_name=_("étiquettes"))
    body = StreamField(
        [
            ("prose", blocks.RichTextBlock(label=_("texte"), features=CONTENT_RICHTEXT_FEATURES)),
            ("callout", CalloutBlock()),
        ],
        blank=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("author"),
        FieldPanel("excerpt"),
        FieldPanel("featured_image"),
        FieldPanel("tags"),
        FieldPanel("body"),
    ]

    parent_page_types = ["cms.PolePage"]
    subpage_types = []

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        # « Saut de page » (bouton dédié de l'éditeur riche, cms/wagtail_hooks.py) :
        # même principe que BlogPostPage.get_context, mais body est un StreamField —
        # seul un <hr class="pagebreak"> à l'intérieur d'un bloc "prose" coupe la page ;
        # un bloc "callout" reste toujours entier sur une seule page (jamais scindé).
        # Les titres de chaque fragment reçoivent une ancre (_add_heading_anchors) au
        # passage, pour le sommaire ci-dessous.
        body_pages = [[]]
        page_headings = [[]]
        seen_slugs = {}
        for block in self.body:
            if block.block_type == "prose":
                fragments = re.split(r'<hr class="pagebreak"\s*/?>', block.value.source)
                for i, fragment in enumerate(fragments):
                    if i > 0:
                        body_pages.append([])
                        page_headings.append([])
                    if fragment.strip():
                        html, headings = _add_heading_anchors(fragment, seen_slugs)
                        body_pages[-1].append({"type": "prose", "html": html})
                        page_headings[-1].extend(headings)
            else:
                body_pages[-1].append({"type": block.block_type, "block": block})
        kept = [(p, h) for p, h in zip(body_pages, page_headings) if p]
        body_pages = [p for p, _ in kept] or [[]]
        page_headings = [h for _, h in kept] or [[]]

        try:
            page_number = int(request.GET.get("page", 1))
        except ValueError:
            page_number = 1
        page_number = max(1, min(page_number, len(body_pages)))
        context["body_pages"] = body_pages
        context["page_number"] = page_number
        context["total_pages"] = len(body_pages)
        # Sommaire limité aux titres de la page actuellement affichée : les autres
        # pages sont masquées à l'écran (content_page.html), un lien d'ancrage vers un
        # titre masqué ne révélerait rien sans JavaScript.
        context["toc"] = page_headings[page_number - 1]

        # « À lire aussi » : par étiquette commune (core.Tag) comme BlogPostPage, sinon
        # d'autres pages du même pôle (ordre de l'arbre Wagtail, pas de date fiable ici
        # puisque ContentPage.date est facultatif).
        my_tag_ids = list(self.tags.values_list("pk", flat=True))
        related = ContentPage.objects.none()
        if my_tag_ids:
            related = (
                ContentPage.objects.live().exclude(pk=self.pk)
                .filter(tags__in=my_tag_ids).distinct().order_by("title")
            )
        related_pages = list(related[:3])
        if len(related_pages) < 3:
            seen_ids = {p.pk for p in related_pages} | {self.pk}
            extra = (
                ContentPage.objects.live().child_of(self.get_parent())
                .exclude(pk__in=seen_ids).order_by("path")
            )
            related_pages += list(extra[: 3 - len(related_pages)])
        context["related_pages"] = related_pages
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


_EXCERPT_BLOCK_RE = re.compile(r"<(?:p|li|h[1-6]|blockquote)[^>]*>(.*?)</(?:p|li|h[1-6]|blockquote)>", re.S)


def excerpt_from_body(html, max_length=280):
    """
    Un chapeau à défaut d'en avoir un (BlogPostPage.get_excerpt) : le premier passage du
    corps d'au moins 40 caractères, pas juste le tout premier fragment — souvent une simple
    date, une salutation ou un titre de section peu représentatif de l'article.
    """
    if not html:
        return ""
    for block in _EXCERPT_BLOCK_RE.findall(html):
        text = re.sub(r"<[^>]+>", "", block)
        text = re.sub(r"\s+", " ", unescape(text)).strip()
        if len(text) >= 40:
            if len(text) > max_length:
                text = text[:max_length].rsplit(" ", 1)[0] + "…"
            return text
    return ""


@register_snippet
class Author(TranslatableMixin, models.Model):
    """
    Autrice ou auteur d'articles de blog — une entité éditoriale indépendante des
    comptes (core.Account) : une même personne peut n'avoir aucun compte sur le site, en
    avoir plusieurs (nominatif et anonymes), ou à l'inverse une même « voix » éditoriale
    (ex. un collectif) peut regrouper plusieurs personnes. Pas de lien vers Account, donc
    — juste un profil affiché sur les articles, choisi librement par qui publie.
    """
    name = models.CharField(_("nom"), max_length=140)
    bio = models.TextField(_("biographie"), blank=True, default="")
    photo = models.ForeignKey(
        "wagtailimages.Image", verbose_name=_("photo"),
        null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    website = models.URLField(_("site web"), blank=True, default="")
    city = models.CharField(_("ville"), max_length=140, blank=True, default="")
    country = models.CharField(_("pays"), max_length=140, blank=True, default="")

    panels = [
        FieldPanel("name"),
        FieldPanel("bio"),
        FieldPanel("photo"),
        FieldPanel("website"),
        FieldPanel("city"),
        FieldPanel("country"),
    ]

    class Meta(TranslatableMixin.Meta):
        verbose_name = _("auteur·ice")
        verbose_name_plural = _("auteur·ices")

    def __str__(self):
        return self.name


class BlogPostPage(Page):
    """
    Un article de blog : texte enrichi, chapeau, image de une et auteur. La
    date affichée (`date`) est distincte de la date de publication Wagtail —
    elle peut être antérieure, notamment pour les articles repris de l'ancien
    blog Ghost.
    """

    date = models.DateTimeField(_("date de publication"), default=timezone.now)
    author = models.ForeignKey(
        Author, verbose_name=_("auteur·ice"),
        null=True, blank=True, on_delete=models.SET_NULL, related_name="blog_posts",
    )
    excerpt = models.CharField(_("chapeau"), max_length=300, blank=True, default="")
    featured = models.BooleanField(_("mis en avant"), default=False)
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
    # Étiquettes partagées avec l'annuaire et les services (core.Tag) : une seule liste
    # de mots-clés pour tout le site (core.views.tag_detail), plutôt qu'un système de
    # tags par section.
    tags = models.ManyToManyField("core.Tag", blank=True, related_name="blog_posts", verbose_name=_("étiquettes"))

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("author"),
        FieldPanel("excerpt"),
        FieldPanel("featured"),
        FieldPanel("featured_image"),
        FieldPanel("tags"),
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
    ]

    parent_page_types = ["cms.BlogIndexPage"]
    subpage_types = []

    def get_excerpt(self):
        return self.excerpt or excerpt_from_body(self.body)

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
        # « À lire aussi » : par étiquette commune (core.Tag) quand il y en a, sinon les
        # plus récents autres articles (billets Ghost importés sans étiquette, par ex).
        my_tag_ids = list(self.tags.values_list("pk", flat=True))
        related = BlogPostPage.objects.none()
        if my_tag_ids:
            related = (
                BlogPostPage.objects.live().exclude(pk=self.pk)
                .filter(tags__in=my_tag_ids).distinct().order_by("-date")
            )
        related_posts = list(related[:3])
        if len(related_posts) < 3:
            seen_ids = {p.pk for p in related_posts} | {self.pk}
            extra = BlogPostPage.objects.live().exclude(pk__in=seen_ids).order_by("-date")
            related_posts += list(extra[: 3 - len(related_posts)])
        context["related_posts"] = related_posts
        return context


@register_snippet
class Announcement(TranslatableMixin, models.Model):
    """
    Bandeau affiché en haut de toutes les pages (core/templates/core/base.html) pendant
    une période donnée, pour mettre en avant une information ponctuelle (fermeture
    exceptionnelle, évènement majeur…). Un seul bandeau actif à la fois par langue — voir
    current(). Traduit à la manière des pages Wagtail (TranslatableMixin) plutôt que par
    modeltranslation : une ligne par langue, avec le bouton « Traduire » de Wagtail
    (wagtail.contrib.simple_translation) pour créer les autres langues à partir du
    français.
    """
    title = models.CharField(_("titre"), max_length=140)
    text = models.CharField(_("texte"), max_length=300, blank=True, default="")
    image = models.ForeignKey(
        "wagtailimages.Image", verbose_name=_("image"),
        null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    page = models.ForeignKey(
        "wagtailcore.Page", verbose_name=_("page liée"),
        null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text=_("Le bandeau pointe vers cette page."),
    )
    publish_start = models.DateField(_("date de début"), null=True, blank=True)
    publish_end = models.DateField(_("date de fin"), null=True, blank=True)
    active = models.BooleanField(_("actif"), default=True)

    panels = [
        FieldPanel("title"),
        FieldPanel("text"),
        FieldPanel("image"),
        FieldPanel("page"),
        FieldPanel("publish_start"),
        FieldPanel("publish_end"),
        FieldPanel("active"),
    ]

    class Meta(TranslatableMixin.Meta):
        verbose_name = _("bandeau d'annonce")
        verbose_name_plural = _("bandeaux d'annonce")

    def __str__(self):
        return self.title

    @classmethod
    def current(cls):
        today = timezone.now().date()
        return (
            cls.objects.filter(locale=Locale.get_active(), active=True)
            .filter(models.Q(publish_start__isnull=True) | models.Q(publish_start__lte=today))
            .filter(models.Q(publish_end__isnull=True) | models.Q(publish_end__gte=today))
            .order_by("-publish_start", "-pk")
            .first()
        )
