from django.db import migrations

# Reprise du blog jusque-là hébergé à part sur Ghost (blog.lesgrandsvoisins.com) : les
# articles eux-mêmes sont importés séparément (voir la commande de gestion
# import_ghost_posts), cette migration ne crée que la page d'index qui les accueille.


def create_blog_index(apps, schema_editor):
    from cms.models import BlogIndexPage, HomePage

    home = HomePage.objects.get(slug="home")
    if BlogIndexPage.objects.filter(slug="blog").exists():
        return
    page = BlogIndexPage(
        title="Blog", draft_title="Blog", slug="blog",
        intro="Les nouvelles et les tribunes des Grands Voisins.",
    )
    home.add_child(instance=page)
    page.save_revision().publish()


def remove_blog_index(apps, schema_editor):
    from cms.models import BlogIndexPage

    BlogIndexPage.objects.filter(slug="blog").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0012_blogindexpage_blogpostpage"),
    ]

    operations = [
        migrations.RunPython(create_blog_index, remove_blog_index),
    ]
