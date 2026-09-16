from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from wagtail.models import Locale

from .models import BlogIndexPage, BlogPostPage
from .qmd import export_blogpost_qmd, import_blogpost_qmd


def _grant_wagtail_admin_access(user):
    # /cms/… exige wagtailadmin.access_admin (require_admin_access) avant même que la vue
    # ne s'exécute — distinct du groupe « Administration » (core), vérifié en plus par
    # qmd_export_view/qmd_import_view eux-mêmes.
    user.user_permissions.add(Permission.objects.get(content_type__app_label="wagtailadmin", codename="access_admin"))


class QmdRoundTripTests(TestCase):
    def setUp(self):
        self.fr = Locale.objects.get(language_code="fr")
        self.blog_index = BlogIndexPage.objects.get(locale=self.fr)
        self.page = BlogPostPage(
            title="Article de test", slug="article-de-test", date=timezone.now(),
            author_name="Voisine", excerpt="Un chapeau.",
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
