"""Convertit BlogPostPage.author_name (texte libre) en cms.Author (entité), avant que
0024 ne supprime l'ancien champ. Un seul Author par valeur de author_name distincte,
créé dans la locale française par défaut (voir cms.models.Author)."""
from django.db import migrations


def backfill_authors(apps, schema_editor):
    BlogPostPage = apps.get_model("cms", "BlogPostPage")
    Author = apps.get_model("cms", "Author")
    Locale = apps.get_model("wagtailcore", "Locale")

    default_locale = Locale.objects.filter(language_code="fr").first() or Locale.objects.first()
    if default_locale is None:
        return

    authors_by_name = {}
    for page in BlogPostPage.objects.exclude(author_name="").exclude(author_name__isnull=True):
        author = authors_by_name.get(page.author_name)
        if author is None:
            author = Author.objects.create(name=page.author_name, locale=default_locale)
            authors_by_name[page.author_name] = author
        page.author = author
        page.save(update_fields=["author"])


def noop(apps, schema_editor):
    # Pas de retour en arrière : les Author créés restent (données utiles), seul le lien
    # author_name -> author se perdrait, ce qui n'a pas besoin d'être annulé explicitement.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0022_author"),
    ]

    operations = [
        migrations.RunPython(backfill_authors, noop),
    ]
