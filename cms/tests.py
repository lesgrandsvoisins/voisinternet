import base64
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.base import ContentFile
from django.core.files.images import ImageFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from wagtail.models import Locale

from .models import Author, BlogIndexPage, BlogPostPage
from .qmd import export_blogpost_qmd, import_blogpost_qmd

# PNG 1x1 valide (Wagtail traite réellement le fichier — génère des renditions — donc un
# contenu bidon ferait échouer Image.objects.create/get_rendition dans les tests).
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _grant_wagtail_admin_access(user):
    # /cms/… exige wagtailadmin.access_admin (require_admin_access) avant même que la vue
    # ne s'exécute — distinct du groupe « Administration » (core), vérifié en plus par
    # qmd_export_view/qmd_import_view eux-mêmes.
    user.user_permissions.add(Permission.objects.get(content_type__app_label="wagtailadmin", codename="access_admin"))


class QmdRoundTripTests(TestCase):
    def setUp(self):
        self.fr = Locale.objects.get(language_code="fr")
        self.blog_index = BlogIndexPage.objects.get(locale=self.fr)
        author = Author.objects.create(name="Voisine", locale=self.fr)
        self.page = BlogPostPage(
            title="Article de test", slug="article-de-test", date=timezone.now(),
            author=author, excerpt="Un chapeau.",
            body="<p>Un <strong>paragraphe</strong> avec une <a href=\"https://example.org\">source</a>.</p>",
        )
        self.blog_index.add_child(instance=self.page)
        self.page.save_revision().publish()

    def test_export_then_import_updates_the_same_page(self):
        qmd = export_blogpost_qmd(self.page)
        self.assertIn(f"key: {self.page.translation_key}", qmd)
        self.assertIn("lang: fr", qmd)

        imported = import_blogpost_qmd(qmd)

        self.assertEqual(imported.pk, self.page.pk)
        self.assertEqual(BlogPostPage.objects.filter(translation_key=self.page.translation_key).count(), 1)
        self.assertIn("paragraphe", imported.body)
        self.assertIn('href="https://example.org"', imported.body)

    def test_import_with_unknown_key_creates_a_new_page(self):
        qmd = (
            "---\n"
            "title: Nouvel article\n"
            "lang: fr\n"
            "slug: nouvel-article\n"
            "---\n\n"
            "Un simple paragraphe.\n"
        )
        page = import_blogpost_qmd(qmd)
        self.assertIsNotNone(page.pk)
        self.assertEqual(page.slug, "nouvel-article")
        self.assertEqual(page.get_parent().specific, self.blog_index)

    def test_import_new_language_creates_a_translation_of_the_existing_key(self):
        en = Locale.objects.get_or_create(language_code="en")[0]
        BlogIndexPage.objects.filter(locale=self.fr).first().copy_for_translation(en, copy_parents=True)

        qmd = (
            "---\n"
            f"key: {self.page.translation_key}\n"
            "lang: en\n"
            "title: Test article\n"
            "slug: test-article\n"
            "---\n\n"
            "A translated paragraph.\n"
        )
        translated = import_blogpost_qmd(qmd)

        self.assertNotEqual(translated.pk, self.page.pk)
        self.assertEqual(translated.translation_key, self.page.translation_key)
        self.assertEqual(translated.locale, en)
        self.assertIn("translated paragraph", translated.body)

    def test_wagtail_image_embed_round_trips_as_a_managed_embed(self):
        from wagtail.images.models import Image

        image = Image.objects.create(title="Photo", file=ImageFile(BytesIO(_PNG_1X1), name="photo.png"))
        self.page.body = f'<embed embedtype="image" id="{image.pk}" format="fullwidth" alt="Une photo"/>'
        self.page.save_revision().publish()

        qmd = export_blogpost_qmd(self.page)
        self.assertIn(f'"wagtail-image:{image.pk}:fullwidth"', qmd)

        imported = import_blogpost_qmd(qmd)
        self.assertIn(f'<embed embedtype="image" id="{image.pk}"', imported.body)
        self.assertIn('alt="Une photo"', imported.body)
        self.assertIn('format="fullwidth"', imported.body)

    def test_document_link_round_trips_as_a_managed_link(self):
        from wagtail.documents.models import Document

        document = Document.objects.create(title="Compte-rendu", file=ContentFile(b"contenu", name="cr.pdf"))
        self.page.body = f'<p>Voir le <a linktype="document" id="{document.pk}">compte-rendu</a>.</p>'
        self.page.save_revision().publish()

        qmd = export_blogpost_qmd(self.page)
        self.assertIn(f'"wagtail-document:{document.pk}"', qmd)

        imported = import_blogpost_qmd(qmd)
        self.assertIn(f'<a linktype="document" id="{document.pk}">compte-rendu</a>', imported.body)

    def test_page_link_round_trips_as_a_managed_link(self):
        target = self.blog_index.get_parent()  # HomePage : forcément déjà là (seed)
        self.page.body = f'<p>Voir <a linktype="page" id="{target.pk}">l\'accueil</a>.</p>'
        self.page.save_revision().publish()

        qmd = export_blogpost_qmd(self.page)
        self.assertIn(f'"wagtail-page:{target.pk}"', qmd)

        imported = import_blogpost_qmd(qmd)
        self.assertIn(f'<a linktype="page" id="{target.pk}">l\'accueil</a>', imported.body)

    def test_pull_quote_span_round_trip(self):
        self.page.body = '<p>Texte avec <span class="pull">une citation en exergue</span> au milieu.</p>'
        self.page.save_revision().publish()

        qmd = export_blogpost_qmd(self.page)
        self.assertIn("[une citation en exergue]{.pull}", qmd)

        imported = import_blogpost_qmd(qmd)
        self.assertIn('<span class="pull">une citation en exergue</span>', imported.body)

    def test_toc_needs_at_least_two_h2(self):
        self.page.body = "<h2>Seul titre</h2><p>Texte.</p>"
        self.page.save_revision().publish()
        response = self.client.get(self.page.url)
        self.assertNotContains(response, 'class="blog-toc')

    def test_toc_covers_every_page_with_page_aware_links(self):
        self.page.body = (
            '<h2>Un</h2><p>a</p><hr class="pagebreak"><h2>Deux</h2><p>b</p>'
        )
        self.page.save_revision().publish()
        response = self.client.get(self.page.url)
        self.assertContains(response, 'class="blog-toc')
        self.assertContains(response, 'id="un"')
        self.assertContains(response, 'href="#un"')  # même page : pas de ?page=
        self.assertContains(response, 'href="?page=2#deux"')  # autre page : ?page= présent

    def test_divider_and_pagebreak_round_trip(self):
        self.page.body = '<p>Avant</p><hr><p>Milieu</p><hr class="pagebreak"><p>Après</p>'
        self.page.save_revision().publish()

        qmd = export_blogpost_qmd(self.page)
        self.assertIn("---\n\nMilieu", qmd)
        self.assertIn("{{< pagebreak >}}", qmd)

        imported = import_blogpost_qmd(qmd)
        self.assertIn("<hr", imported.body)
        self.assertIn('class="pagebreak"', imported.body)


class QmdAdminViewsTests(TestCase):
    """Boutons « Exporter/Importer .qmd » sur l'écran d'édition d'un article (voir
    cms/wagtail_hooks.py : qmd_header_buttons, qmd_export_view, qmd_import_view)."""

    def setUp(self):
        self.fr = Locale.objects.get(language_code="fr")
        self.blog_index = BlogIndexPage.objects.get(locale=self.fr)
        self.page = BlogPostPage(title="Article", slug="article", date=timezone.now(), body="<p>Texte</p>")
        self.blog_index.add_child(instance=self.page)
        self.page.save_revision().publish()

    def test_ordinary_user_is_refused(self):
        # Accès Wagtail admin (/cms/) mais pas membre du groupe « Administration » : la
        # vue elle-même refuse (PermissionDenied) — require_admin_access la convertit en
        # redirection vers l'accueil de l'admin (pas un 403 brut, comportement Wagtail
        # standard : voir wagtail.admin.auth.permission_denied).
        user = get_user_model().objects.create_user("voisine")
        _grant_wagtail_admin_access(user)
        self.client.force_login(user)
        self.assertRedirects(
            self.client.get(reverse("blog_qmd_export", args=[self.page.pk])), reverse("wagtailadmin_home"),
        )
        self.assertRedirects(
            self.client.get(reverse("blog_qmd_import", args=[self.page.pk])), reverse("wagtailadmin_home"),
        )

    def test_administration_group_member_can_export_and_reimport(self):
        admin_user = get_user_model().objects.create_user("admin")
        admin_user.groups.add(Group.objects.get(name="Administration"))
        _grant_wagtail_admin_access(admin_user)
        self.client.force_login(admin_user)

        response = self.client.get(reverse("blog_qmd_export", args=[self.page.pk]))
        self.assertEqual(response.status_code, 200)
        qmd = response.content.decode()
        self.assertIn(f"key: {self.page.translation_key}", qmd)

        upload = BytesIO(qmd.encode("utf-8"))
        upload.name = "article.qmd"
        response = self.client.post(reverse("blog_qmd_import", args=[self.page.pk]), {"qmd_file": upload})
        self.assertRedirects(response, reverse("wagtailadmin_pages:edit", args=[self.page.pk]), fetch_redirect_response=False)
        # Même clé : mise à jour de l'article existant, pas de doublon.
        self.assertEqual(BlogPostPage.objects.filter(translation_key=self.page.translation_key).count(), 1)

    def test_importing_a_file_for_another_key_redirects_to_that_other_page(self):
        other = BlogPostPage(title="Autre article", slug="autre-article", date=timezone.now(), body="<p>Autre</p>")
        self.blog_index.add_child(instance=other)
        other.save_revision().publish()

        admin_user = get_user_model().objects.create_user("admin2")
        admin_user.groups.add(Group.objects.get(name="Administration"))
        _grant_wagtail_admin_access(admin_user)
        self.client.force_login(admin_user)

        qmd = export_blogpost_qmd(other)
        upload = BytesIO(qmd.encode("utf-8"))
        upload.name = "autre-article.qmd"
        # Importé depuis l'écran de `self.page`, mais le fichier porte la clé de `other`.
        response = self.client.post(reverse("blog_qmd_import", args=[self.page.pk]), {"qmd_file": upload})
        self.assertRedirects(response, reverse("wagtailadmin_pages:edit", args=[other.pk]), fetch_redirect_response=False)

    def test_export_import_buttons_appear_in_the_page_listing(self):
        # Superuser (pas juste wagtailadmin.access_admin) : la vue de listing exige en
        # plus les permissions Wagtail par page (voir GroupPagePermission), hors sujet ici.
        admin_user = get_user_model().objects.create_superuser("admin3", "admin3@example.com", "pass12345")
        admin_user.groups.add(Group.objects.get(name="Administration"))
        self.client.force_login(admin_user)

        response = self.client.get(reverse("wagtailadmin_explore", args=[self.blog_index.pk]))
        self.assertContains(response, reverse("blog_qmd_export", args=[self.page.pk]))
        self.assertContains(response, reverse("blog_qmd_import", args=[self.page.pk]))

    def test_export_zip_requires_administration_group(self):
        user = get_user_model().objects.create_user("voisine2")
        _grant_wagtail_admin_access(user)
        self.client.force_login(user)
        self.assertRedirects(
            self.client.get(reverse("blog_qmd_export_zip")), reverse("wagtailadmin_home"),
        )

    def test_export_zip_bundles_every_article_and_its_media(self):
        import zipfile

        from wagtail.images.models import Image

        image = Image.objects.create(title="Photo", file=ImageFile(BytesIO(_PNG_1X1), name="photo.png"))
        self.page.body = f'<embed embedtype="image" id="{image.pk}" format="fullwidth" alt="Une photo"/>'
        self.page.save_revision().publish()

        admin_user = get_user_model().objects.create_user("admin4")
        admin_user.groups.add(Group.objects.get(name="Administration"))
        _grant_wagtail_admin_access(admin_user)
        self.client.force_login(admin_user)

        response = self.client.get(reverse("blog_qmd_export_zip"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        zf = zipfile.ZipFile(BytesIO(response.content))
        names = zf.namelist()
        self.assertIn("fr/article.qmd", names)
        self.assertTrue(any(n.startswith(f"media/images/{image.pk}-") for n in names))
        # Le .qmd du zip référence bien un chemin local (pas une URL) pour cette image.
        qmd_in_zip = zf.read("fr/article.qmd").decode()
        self.assertIn(f'(media/images/{image.pk}-', qmd_in_zip)
        self.assertIn(f'"wagtail-image:{image.pk}:fullwidth"', qmd_in_zip)
