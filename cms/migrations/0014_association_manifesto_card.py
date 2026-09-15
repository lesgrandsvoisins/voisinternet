"""
Ajoute le texte complet du manifeste (écrit collectivement par une centaine de
personnes en 2017) à la page Association, qui n'en avait jusqu'ici qu'un résumé
(carte « Notre raison d'être », cms.migrations.0008_seed_more_pages). Source :
wiki interne (fr/association/manifeste.md).
"""
from django.db import migrations

MANIFESTO_HTML = (
    "<p>Ce manifeste, imparfait, reflète les espérances, les souffrances et les "
    "incompréhensions de ceux qui l'ont insufflé. Les Grands Voisins sont nés à "
    "l'hôpital Saint-Vincent-de-Paul dans le 14e arrondissement à Paris, entre Port "
    "royal et les Catacombes. Nous sommes issus des failles dans le béton et dans "
    "les politiques publiques. Nous sommes au service de l'accueil de tous et "
    "croyons aux ponts entre utopie et réalité.</p>"
    "<p>Comme toutes bonnes voisines et tous bons voisins, nous ne sommes pas "
    "toujours d'accord entre nous, mais nous défendons :</p>"
    "<ul>"
    "<li>la parité dans la gouvernance</li>"
    "<li>des solutions collectives en bonne intelligence</li>"
    "<li>l'expression libre</li>"
    "<li>l'exercice artistique</li>"
    "<li>l'apprentissage tout au long de la vie</li>"
    "<li>la valorisation de toutes formes de travail</li>"
    "</ul>"
    "<p>Aux Grands Voisins, nous vivons, travaillons, dormons, mangeons, nous "
    "soignons, achetons, pleurons, rions, et tout cela dans toutes les langues. "
    "L'inclusion et l'exclusion, toutes les deux, peuvent nous éloigner de l'Autre "
    "qui est une chance.</p>"
    "<p>Nous réclamons des lieux de mixité sociale qui permettent la valorisation "
    "et le partage des savoirs et des savoir-faire de toutes et de tous, qui "
    "favorisent l'écoute et les possibilités de rencontre — conditions visant à "
    "l'abolition de la peur de l'autre —, et qui luttent contre « l'entre-soi », "
    "l'isolement et la réduction des individus à des cases.</p>"
    "<p>Nous avons besoin de lieux et de temps pour faire précédent, pouvoir "
    "inventer d'autres formes de société en harmonie avec les écosystèmes. Nous "
    "avons toutes et tous à donner et nous pouvons toutes et tous recevoir.</p>"
)


def add_manifesto(apps, schema_editor):
    from cms.models import AssociationPage

    page = AssociationPage.objects.filter(slug="grandsvoisins").first()
    if page is None:
        return

    already_present = any(
        block.block_type == "card" and block.value.get("title") == "Notre manifeste"
        for block in page.body
    )
    if already_present:
        return

    insert_at = 2  # après « Notre raison d'être » et « D'où nous venons ».
    page.body.insert(insert_at, ("card", {"title": "Notre manifeste", "text": MANIFESTO_HTML}))
    page.save_revision().publish()


def remove_manifesto(apps, schema_editor):
    from cms.models import AssociationPage

    page = AssociationPage.objects.filter(slug="grandsvoisins").first()
    if page is None:
        return

    for i, block in enumerate(page.body):
        if block.block_type == "card" and block.value.get("title") == "Notre manifeste":
            del page.body[i]
            page.save_revision().publish()
            break


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0013_seed_blog_index"),
    ]

    operations = [
        migrations.RunPython(add_manifesto, remove_manifesto),
    ]
