"""
Une douzaine d'articles importés de Ghost avaient un chapeau peu informatif — une simple
date/lieu, « Ordre du Jour », « Objectifs: » ou une salutation — au lieu d'une vraie
accroche : la première ligne du Markdown d'origine, pas forcément représentative. Reprend
soit la première phrase substantielle du corps de l'article (≥ 40 caractères), soit un
résumé écrit à la main quand ce premier passage venait mal (ordre du jour brut, liste
d'actions sans phrase d'ensemble).
"""
from django.db import migrations

NEW_EXCERPTS = {
    "11e-conseil-des-voisins": (
        "Lors du Conseil ven. 18 mars à 18h (2022) à la Ressourcerie créative (14e) et en "
        "ligne, nous avions abordé plusieurs sujets."
    ),
    "12e-conseil-des-voisins": (
        "Venez nous voir en personne Chez Papa 138 boulevard de Montparnasse 75014 Paris, "
        "ou en ligne."
    ),
    "13e-conseil-des-voisins": (
        "Orientations présentées et approuvées : création de l'association, poursuite du "
        "budget participatif pour une salle de sociabilité numérique, et poursuite des "
        "Popup Expos."
    ),
    "16e-conseil-des-voisins": (
        "Ordre du jour : lancement du nouveau site lesgrandsvoisins.com, reconnaissance en "
        "coopérative, lancement des Popup Expos et de la salle de sociabilité numérique."
    ),
    "4e-conseil-des-voisins": (
        "Chris Mann, Sabine de la Ressourcerie Créative, Gabriele Santini, Juan Marcos, "
        "Peter Dewit, Thomas Egret et d'autres voisins étaient présents."
    ),
    "hasard-de-marque": (
        "J'ai déposé les noms de domaine .com et .fr suite aux débats concernant le "
        "manifeste. J'ai trouvé pertinent d'expliquer pourquoi."
    ),
    "les-grands-voisins-sont-morts-vive-les-grands-voisins": (
        "Les Grands Voisins est un concept sur quatre piliers."
    ),
    "merc-27-oct-21-19h30-a-21h-les-grands-voisins-a-bagneux-et-en-viseo": (
        "J'ai le grand plaisir de vous inviter à la réunion Les Grands Voisins ce mercredi "
        "27 octobre 2021."
    ),
    "popup-expos-2": "Favoriser une vie de quartier selon les principes des Grands Voisins.",
    "salle-de-sociabilite-numerique-au-chu-emmaus-jourdan": (
        "Lancement, le 14 juin 2024, du numérique créatif des Grands Voisins au service du "
        "CHU Emmaüs Jourdan : une expérimentation de trois mois pour outiller les "
        "travailleurs sociaux d'une salle de sociabilité numérique."
    ),
}


def update_excerpts(apps, schema_editor):
    # Modèle historique (pas cms.models.BlogPostPage) : ses colonnes reflètent l'état de
    # la base à ce point précis de l'historique, contrairement au modèle actuel, qui
    # casserait sur une base neuve dès qu'un champ est ajouté après cette migration.
    # save_revision().publish() (machinerie Wagtail complète) n'est donc pas disponible
    # ici — une simple sauvegarde suffit pour ce correctif ponctuel de contenu.
    BlogPostPage = apps.get_model("cms", "BlogPostPage")

    for slug, excerpt in NEW_EXCERPTS.items():
        page = BlogPostPage.objects.filter(slug=slug).first()
        if page is None:
            continue
        page.excerpt = excerpt[:300]
        page.save()


def noop(apps, schema_editor):
    # Pas de retour en arrière : on ne garde pas les anciens chapeaux peu utiles.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0017_pole_content_from_wiki"),
    ]

    operations = [
        migrations.RunPython(update_excerpts, noop),
    ]
