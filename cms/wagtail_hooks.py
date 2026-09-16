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
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import path, reverse, reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin import widgets as wagtailadmin_widgets
from wagtail.admin.rich_text.converters.contentstate_models import Entity
from wagtail.admin.rich_text.converters.html_to_contentstate import AtomicBlockEntityElementHandler
from wagtail.admin.rich_text.editors.draftail import features as draftail_features

from .models import BlogIndexPage, BlogPostPage
from .qmd import export_blog_zip, export_blogpost_qmd, import_blogpost_qmd


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


def _can_manage_qmd(user):
    return user.is_active and (user.is_superuser or user.groups.filter(name="Administration").exists())


@hooks.register("register_page_header_buttons")
def qmd_header_buttons(page, user, view_name, next_url=None):
    """
    Boutons « Exporter/Importer .qmd » sur l'écran d'édition d'un article de blog, et
    « Exporter tout le blog (.zip) » sur celui d'une page d'index de blog (voir
    cms/qmd.py) — pas sur les autres types de page, qui n'ont pas de body exportable de
    la même façon.
    """
    specific = getattr(page, "specific", page)
    if not _can_manage_qmd(user):
        return
    if isinstance(specific, BlogPostPage):
        yield wagtailadmin_widgets.Button(
            _("Exporter .qmd"), reverse("blog_qmd_export", args=[specific.pk]), icon_name="download", priority=70,
        )
        yield wagtailadmin_widgets.Button(
            _("Importer .qmd"), reverse("blog_qmd_import", args=[specific.pk]), icon_name="upload", priority=71,
        )
    elif isinstance(specific, BlogIndexPage):
        yield wagtailadmin_widgets.Button(
            _("Exporter tout le blog (.zip)"), reverse("blog_qmd_export_zip"), icon_name="download", priority=70,
        )


@hooks.register("register_page_listing_more_buttons")
def qmd_listing_more_buttons(page, user, next_url=None):
    """Mêmes actions que qmd_header_buttons, mais depuis le listing des pages (menu « … »
    de chaque ligne) — pratique pour agir sur plusieurs articles sans ouvrir chacun."""
    specific = getattr(page, "specific", page)
    if not _can_manage_qmd(user):
        return
    if isinstance(specific, BlogPostPage):
        yield wagtailadmin_widgets.Button(
            _("Exporter .qmd"), reverse("blog_qmd_export", args=[specific.pk]), icon_name="download", priority=70,
        )
        yield wagtailadmin_widgets.Button(
            _("Importer .qmd"), reverse("blog_qmd_import", args=[specific.pk]), icon_name="upload", priority=71,
        )
    elif isinstance(specific, BlogIndexPage):
        yield wagtailadmin_widgets.Button(
            _("Exporter tout le blog (.zip)"), reverse("blog_qmd_export_zip"), icon_name="download", priority=70,
        )


def qmd_export_zip_view(request):
    if not _can_manage_qmd(request.user):
        raise PermissionDenied
    response = HttpResponse(export_blog_zip(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="blog.zip"'
    return response


def qmd_export_view(request, pk):
    if not _can_manage_qmd(request.user):
        raise PermissionDenied
    page = get_object_or_404(BlogPostPage, pk=pk)
    response = HttpResponse(export_blogpost_qmd(page), content_type="text/markdown; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{page.slug}.qmd"'
    return response


def qmd_import_view(request, pk):
    if not _can_manage_qmd(request.user):
        raise PermissionDenied
    page = get_object_or_404(BlogPostPage, pk=pk)

    if request.method == "POST":
        uploaded = request.FILES.get("qmd_file")
        if not uploaded:
            messages.error(request, _("Choisissez un fichier .qmd à importer."))
        else:
            try:
                imported = import_blogpost_qmd(uploaded.read().decode("utf-8"))
            except Exception as exc:
                # Fichier fourni par la personne (contenu non fiable) : toute erreur de
                # lecture doit rester un message, jamais une page 500.
                messages.error(request, _("Échec de l'import : %(error)s") % {"error": exc})
            else:
                if imported.pk == page.pk:
                    messages.success(request, _("Article mis à jour depuis le fichier .qmd."))
                else:
                    messages.warning(
                        request,
                        _(
                            "Le fichier .qmd portait la clé d'un autre article : « %(title)s » a été "
                            "créé ou mis à jour à la place de celui-ci."
                        ) % {"title": imported.title},
                    )
                return redirect("wagtailadmin_pages:edit", imported.pk)

    return render(request, "cms/admin/qmd_import.html", {"page": page, "view_title": _("Importer un .qmd")})


@hooks.register("register_admin_urls")
def register_qmd_admin_urls():
    return [
        path("blog-qmd/<int:pk>/export/", qmd_export_view, name="blog_qmd_export"),
        path("blog-qmd/<int:pk>/import/", qmd_import_view, name="blog_qmd_import"),
        path("blog-qmd/export-zip/", qmd_export_zip_view, name="blog_qmd_export_zip"),
    ]
