"""
Amorce le système d'étiquettes partagé (core.Tag) : une étiquette par pôle, appliquée au
pôle lui-même et à quelques articles de blog déjà publiés qui s'y rattachent clairement —
de quoi voir tout de suite le rapprochement blog/pôle (PolePage.get_context) fonctionner,
plutôt que partir d'une liste vide. Rien n'empêche d'en ajouter d'autres ensuite depuis
l'admin.
"""
from django.db import migrations

# slug de PolePage -> (nom de l'étiquette, slugs d'articles de blog déjà publiés à lier)
POLE_TAGS = {
    "civisme": ("Civisme", ["pour-nous-etrangers-la-vraie-france"]),
    "arts-plastiques": (
        "Arts plastiques",
        ["hommage-a-arakaki-dim-6-avril-a-houilles", "galerie-les-arts-voisins-a-ladapt-chatillon", "popup-expos"],
    ),
    "numerique": ("Numérique", ["paris-le-nuage"]),
}


def slugify_simple(name):
    from django.utils.text import slugify

    return slugify(name)


def seed_tags(apps, schema_editor):
    Tag = apps.get_model("core", "Tag")
    PolePage = apps.get_model("cms", "PolePage")
    BlogPostPage = apps.get_model("cms", "BlogPostPage")

    for pole_slug, (tag_name, post_slugs) in POLE_TAGS.items():
        tag, _created = Tag.objects.get_or_create(slug=slugify_simple(tag_name), defaults={"name": tag_name})
        pole = PolePage.objects.filter(slug=pole_slug).first()
        if pole:
            pole.tags.add(tag)
        for post_slug in post_slugs:
            post = BlogPostPage.objects.filter(slug=post_slug).first()
            if post:
                post.tags.add(tag)


def unseed_tags(apps, schema_editor):
    Tag = apps.get_model("core", "Tag")
    Tag.objects.filter(slug__in=[slugify_simple(name) for name, _ in POLE_TAGS.values()]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0015_blogpostpage_tags_polepage_tags_projectpage"),
        ("core", "0022_tag_directoryentry_layout_directoryentry_tags_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_tags, unseed_tags),
    ]
