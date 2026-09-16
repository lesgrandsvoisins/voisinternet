"""
Corrige une régression de core.migrations.0018 : le champ « approved » (validation du
groupe Administration) a été ajouté avec `default=False` sans mettre à jour les fiches
déjà publiques à ce moment-là, qui sont donc toutes devenues invisibles (annuaire,
fiche, recherche) du jour au lendemain — sans qu'aucune administratrice n'ait rien
demandé ni refusé. On considère ici que toute fiche déjà publique le reste : c'était son
état de fait avant l'ajout de la validation, il n'y a pas de raison de le remettre en
cause rétroactivement. Seules les demandes de publication FUTURES (core.views.
toggle_publication) repassent par la validation, comme prévu.
"""
from django.db import migrations


def backfill(apps, schema_editor):
    DirectoryEntry = apps.get_model("core", "DirectoryEntry")
    DirectoryEntry.objects.filter(visibility="public", approved=False).update(approved=True)


def noop(apps, schema_editor):
    # Non réversible en toute rigueur (on ne sait plus lesquelles étaient approuvées
    # avant cette migration) : ne rien défaire plutôt que tout re-cacher à tort.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0024_populate_tags"),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
