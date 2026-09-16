"""
Enrichit les trois pôles avec du contenu réel tiré du wiki interne (fr/civisme/empathie.md,
fr/arts-plastiques.md, fr/numerique/sociabilite-numerique/presentation.md) — sans reprendre
les horaires/dates qui divergent d'une source à l'autre (wiki, site en production) tant
qu'ils n'ont pas été confirmés.
"""
from django.db import migrations

NEW_CARDS = {
    "civisme": (
        "Le prix Annette Monod-Leiris",
        "<p>La journée « Profession d'Empathie Nationale » est aussi celle de la remise "
        "du prix Annette Monod-Leiris, qui reconnaît l'excellence en travail social — "
        "dans une catégorie bénévolat et une catégorie profession — en mémoire de "
        "Valentin Francy.</p>",
    ),
    "arts-plastiques": (
        "Pourquoi des Popup Expos",
        "<p>Inviter l'art hors les murs, c'est-à-dire dans des lieux où on ne l'attend "
        "pas :</p><ul>"
        "<li>donne une autre vision du quotidien</li>"
        "<li>anime les murs</li>"
        "<li>propose une évasion</li>"
        "<li>valorise nos patrimoines, nos cultures et nos artistes</li>"
        "</ul>",
    ),
    "numerique": (
        "Qui peut venir",
        "<p>Tous niveaux, tous âges, tous besoins sont les bienvenus : des craintifs du "
        "numérique aux ingénieurs informaticiens, des sans-ordinateur aux équipés du nec "
        "plus ultra, des hébergés ou migrants aux propriétaires ou entreprises du "
        "quartier, des étudiants aux retraités.</p>",
    ),
}


def add_cards(apps, schema_editor):
    from cms.models import PolePage

    for pole_slug, (title, text) in NEW_CARDS.items():
        page = PolePage.objects.filter(slug=pole_slug).first()
        if page is None:
            continue
        already = any(
            block.block_type == "card" and block.value.get("title") == title for block in page.cards
        )
        if already:
            continue
        page.cards.append(("card", {"title": title, "text": text}))
        page.save_revision().publish()


def remove_cards(apps, schema_editor):
    from cms.models import PolePage

    for pole_slug, (title, _text) in NEW_CARDS.items():
        page = PolePage.objects.filter(slug=pole_slug).first()
        if page is None:
            continue
        for i, block in enumerate(page.cards):
            if block.block_type == "card" and block.value.get("title") == title:
                del page.cards[i]
                page.save_revision().publish()
                break


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0016_seed_tags"),
    ]

    operations = [
        migrations.RunPython(add_cards, remove_cards),
    ]
