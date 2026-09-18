from django.db import migrations

# Reprise du contenu jusque-là codé en dur dans core/templates/core/{civisme,
# arts-plastiques,numerique}.html et core/views.py (BLOG_TAGS), avant leur
# passage sous Wagtail.
POLES = [
    {
        "slug": "civisme",
        "title": "Civisme",
        "lead": "S'engager pour l'intérêt général, entre voisins.",
        "accent": "terracotta",
        "ghost_tag": "cooperations",
        "cards": [
            (
                "Profession d'Empathie Nationale",
                "<p>Un événement annuel, tenu chaque 2 mars depuis 2025, en hommage à Valentin Francy. "
                "Il récompense l'excellence dans le travail social par le prix Annette Monod. "
                "L'édition 2025 s'est tenue à l'association France Amérique-Latine.</p>",
            ),
        ],
    },
    {
        "slug": "arts-plastiques",
        "title": "Arts plastiques",
        "lead": "Transformer tout lieu en galerie d'art hybride.",
        "accent": "plum",
        "ghost_tag": "[arts,arts-plastiques]",
        "cards": [
            (
                "Popup Expos",
                "<p>Le principe : transformer n'importe quel lieu en galerie d'art hybride, "
                "le temps d'une exposition.</p>",
            ),
            (
                "Galerie Les Arts Voisins à LADAPT Châtillon",
                "<p>Décembre 2025 : une galerie d'art installée dans un centre de rééducation, "
                "pour sensibiliser le public et relier l'expression artistique aux parcours de soin.</p>",
            ),
            (
                "Hommage à Arakaki",
                "<p>Avril 2025 : un hommage au peintre et écrivain Félix Toshi Arakaki, dans sa "
                "maison-atelier de Houilles, avec la participation de sa famille et du voisinage.</p>",
            ),
            (
                "Tableaux & roman « La Macha »",
                "<p>31 janvier et 1er février 2025 : une exposition de tableaux autour du roman "
                "« La Macha ».</p>",
            ),
        ],
    },
    {
        "slug": "numerique",
        "title": "Numérique",
        "lead": "Revalorisation en numérique : matériel reconditionné et compétences partagées.",
        "accent": "indigo",
        "ghost_tag": "digital",
        "cards": [
            (
                "Revalorisation en numérique",
                '<p>Reconditionnement d\'ordinateurs et montée en compétences numériques. '
                'Inscrivez-vous sur <a href="https://gdvoisins.com" target="_new">gdvoisins.com</a>.</p>',
            ),
            (
                "Paris le Nuage",
                "<p>Remplacer les services des géants du web par des petits serveurs à la maison, "
                "peu gourmands en énergie, pour ses fichiers et ses photos. C'est très exactement "
                "ce que propose Voisinternet.</p>",
            ),
        ],
    },
]


def create_pole_pages(apps, schema_editor):
    # Page.add_child()/copy() s'appuient sur treebeard et sur le save() de
    # Page (cf. cms.0002_create_homepage) : on importe donc les vraies classes.
    from cms.models import HomePage, PolePage

    home = HomePage.objects.get(slug="home")

    for pole in POLES:
        if PolePage.objects.filter(slug=pole["slug"]).exists():
            continue
        page = PolePage(
            title=pole["title"],
            draft_title=pole["title"],
            slug=pole["slug"],
            lead=pole["lead"],
            accent=pole["accent"],
            ghost_tag=pole["ghost_tag"],
            cards=[{"type": "card", "value": {"title": t, "text": text}} for t, text in pole["cards"]],
        )
        home.add_child(instance=page)
        page.save_revision().publish()


def remove_pole_pages(apps, schema_editor):
    from cms.models import PolePage

    PolePage.objects.filter(slug__in=[pole["slug"] for pole in POLES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        # Voir cms/migrations/0032_polepage_legacy_meta_early.py : cette migration
        # utilise le modèle PolePage courant (from cms.models import) avant sa place
        # chronologique réelle dans l'historique.
        ("cms", "0032_polepage_legacy_meta_early"),
    ]

    operations = [
        migrations.RunPython(create_pole_pages, remove_pole_pages),
    ]
