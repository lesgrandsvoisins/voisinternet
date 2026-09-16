from django.test import TestCase
from django.utils import timezone
from wagtail.models import Locale

from .models import BlogIndexPage, BlogPostPage
from .qmd import export_blogpost_qmd, import_blogpost_qmd


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
