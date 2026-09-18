"""
Convertit les cartes de pôle qui décrivaient un projet ou un évènement précis en vraies
pages ProjectPage (chapeau + corps, avec leur propre URL) plutôt que de simples blocs de
texte sans destination — reprend le texte déjà rédigé tel quel, ne invente aucun contenu
nouveau. Les cartes plus générales (qui ne décrivent pas un projet précis) restent des
cartes de pôle ordinaires.
"""
import datetime

from django.db import migrations
from django.utils.text import slugify

# slug de PolePage -> liste de (titre de la page, lead, [(titre de carte, texte)], date_start, date_end, location)
# Les paires (titre de carte, texte) à retirer de PolePage.cards sont fournies telles
# quelles pour devenir des blocs "card" du corps de la nouvelle page.
PROJECTS = {
    "civisme": [
        (
            "Profession d'Empathie Nationale",
            "Un événement annuel en hommage à Valentin Francy, avec le prix Annette Monod-Leiris pour l'excellence en travail social.",
            [
                "Profession d'Empathie Nationale",
                "Le prix Annette Monod-Leiris",
            ],
            datetime.date(2025, 3, 2), None, "",
        ),
    ],
    "arts-plastiques": [
        (
            "Popup Expos",
            "Transformer n'importe quel lieu en galerie d'art hybride, le temps d'une exposition.",
            ["Popup Expos", "Pourquoi des Popup Expos"],
            None, None, "",
        ),
        (
            "Galerie Les Arts Voisins à LADAPT Châtillon",
            "Une galerie d'art installée dans un centre de rééducation, pour sensibiliser le public et relier l'expression artistique aux parcours de soin.",
            ["Galerie Les Arts Voisins à LADAPT Châtillon"],
            datetime.date(2025, 12, 30), None, "LADAPT Châtillon",
        ),
        (
            "Hommage à Arakaki",
            "Un hommage au peintre et écrivain Félix Toshi Arakaki, dans sa maison-atelier de Houilles, avec la participation de sa famille et du voisinage.",
            ["Hommage à Arakaki"],
            datetime.date(2025, 4, 6), None, "Houilles",
        ),
        (
            "Tableaux & roman « La Macha »",
            "Une exposition de tableaux autour du roman « La Macha ».",
            ["Tableaux & roman « La Macha »"],
            datetime.date(2025, 1, 31), datetime.date(2025, 2, 1), "",
        ),
    ],
    "numerique": [
        (
            "Revalorisation en numérique",
            "Reconditionnement d'ordinateurs et montée en compétences numériques.",
            ["Revalorisation en numérique"],
            None, None, "",
        ),
        (
            "Paris le Nuage",
            "Remplacer les services des géants du web par des petits serveurs à la maison, peu gourmands en énergie.",
            ["Paris le Nuage"],
            None, None, "",
        ),
    ],
}


def unique_slug(model, base):
    slug = slugify(base) or "projet"
    candidate = slug
    suffix = 1
    while model.objects.filter(slug=candidate).exists():
        suffix += 1
        candidate = f"{slug}-{suffix}"
    return candidate


def convert(apps, schema_editor):
    from cms.models import PolePage, ProjectPage

    for pole_slug, projects in PROJECTS.items():
        pole = PolePage.objects.filter(slug=pole_slug).first()
        if pole is None:
            continue
        cards_by_title = {b.value["title"]: b.value["text"] for b in pole.cards if b.block_type == "card"}

        for title, lead, card_titles, date_start, date_end, location in projects:
            if ProjectPage.objects.filter(slug=slugify(title)).exists():
                continue
            body = [
                ("card", {"title": t, "text": cards_by_title[t]})
                for t in card_titles if t in cards_by_title
            ]
            if not body:
                continue
            project = ProjectPage(
                title=title, draft_title=title, slug=unique_slug(ProjectPage, title),
                lead=lead, date_start=date_start, date_end=date_end, location=location,
                body=body,
            )
            pole.add_child(instance=project)
            project.save_revision().publish()

            remaining = [
                ("card", {"title": b.value["title"], "text": b.value["text"]})
                for b in pole.cards
                if b.block_type != "card" or b.value["title"] not in card_titles
            ]
            pole.cards = remaining
            pole.save_revision().publish()
            pole.refresh_from_db()


def revert(apps, schema_editor):
    from cms.models import PolePage, ProjectPage

    for pole_slug, projects in PROJECTS.items():
        pole = PolePage.objects.filter(slug=pole_slug).first()
        for title, lead, card_titles, date_start, date_end, location in projects:
            project = ProjectPage.objects.filter(title=title).child_of(pole).first() if pole else None
            if project:
                project.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0018_fix_poor_excerpts"),
    ]

    operations = [
        migrations.RunPython(convert, revert),
    ]
