"""
Étend le peuplement des étiquettes (cms.migrations.0016_seed_tags, qui n'avait fait que le
blog) à l'annuaire — DirectorySector a déjà les mêmes trois secteurs (civisme,
arts-plastiques, numerique) que les étiquettes de pôle, il suffit de reprendre ce
classement existant plutôt que de deviner — et à l'agenda, au cas par cas d'après le
titre et la description de chaque évènement.
"""
from django.db import migrations

# slug de DirectorySector -> slug de Tag (identiques ici, mais explicite plutôt que supposé).
SECTOR_TO_TAG = {
    "civisme": "civisme",
    "arts-plastiques": "arts-plastiques",
    "numerique": "numerique",
}

# Titre d'Event (exact) -> slug de Tag, d'après leur description (voir le commentaire
# ci-dessous pour la justification de chacun).
EVENT_TAGS = {
    # « Nous mettons l'accent cette année sur les arts plastiques avec une animation… »
    "Fête de la Banane (9e édition)": "arts-plastiques",
    # Conseil des Voisins / prix d'excellence en travail social : gouvernance et
    # reconnaissance associative, comme le prix Annette Monod-Leiris déjà lié à Civisme.
    "27e Conseil des Voisins (13h)": "civisme",
    "27e Conseil des Voisins (18h)": "civisme",
    "Remise de prix pour excellence en travail social": "civisme",
}


def populate(apps, schema_editor):
    Tag = apps.get_model("core", "Tag")
    DirectoryEntry = apps.get_model("core", "DirectoryEntry")
    Event = apps.get_model("core", "Event")

    tags_by_slug = {t.slug: t for t in Tag.objects.filter(slug__in=SECTOR_TO_TAG.values())}

    for sector_slug, tag_slug in SECTOR_TO_TAG.items():
        tag = tags_by_slug.get(tag_slug)
        if tag is None:
            continue
        for entry in DirectoryEntry.objects.filter(sector__slug=sector_slug):
            entry.tags.add(tag)

    for title, tag_slug in EVENT_TAGS.items():
        tag = tags_by_slug.get(tag_slug)
        if tag is None:
            continue
        for event in Event.objects.filter(title=title):
            event.tags.add(tag)


def unpopulate(apps, schema_editor):
    Tag = apps.get_model("core", "Tag")
    DirectoryEntry = apps.get_model("core", "DirectoryEntry")
    Event = apps.get_model("core", "Event")

    tags_by_slug = {t.slug: t for t in Tag.objects.filter(slug__in=SECTOR_TO_TAG.values())}
    for sector_slug, tag_slug in SECTOR_TO_TAG.items():
        tag = tags_by_slug.get(tag_slug)
        if tag is None:
            continue
        for entry in DirectoryEntry.objects.filter(sector__slug=sector_slug):
            entry.tags.remove(tag)
    for title, tag_slug in EVENT_TAGS.items():
        tag = tags_by_slug.get(tag_slug)
        if tag is None:
            continue
        for event in Event.objects.filter(title=title):
            event.tags.remove(tag)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0023_event_tags"),
        ("cms", "0016_seed_tags"),
    ]

    operations = [
        migrations.RunPython(populate, unpopulate),
    ]
