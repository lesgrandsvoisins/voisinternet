# Ajoute PolePage.legacy_meta bien plus tôt dans l'historique que sa place chronologique
# réelle (cms.0031_legacy_meta) : cms.0006_seed_pole_pages (et plusieurs migrations
# suivantes — 0010, 0017, 0019…) importent `from cms.models import PolePage` (le modèle
# COURANT, pas apps.get_model) pour manipuler de vraies pages Wagtail (StreamField,
# add_child, save_revision/publish — indisponibles sur un modèle historique). Sur une
# base migrée depuis zéro (make test, nouvelle installation), le modèle courant connaît
# déjà ce champ alors que la colonne n'existe pas avant ce point de l'historique, et
# toute requête posée avec ce modèle échoue ("no such column"). Dépend directement de
# 0005 (création de PolePage) et 0006 en dépend à la place de 0005, pour que la colonne
# existe dès la première utilisation du modèle courant. Voir aussi
# 0033_projectpage_legacy_meta_early.py pour le même besoin côté ProjectPage — deux
# fichiers séparés parce que ProjectPage n'existe pas encore à ce point-ci.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0005_polepage'),
    ]

    operations = [
        migrations.AddField(
            model_name='polepage',
            name='legacy_meta',
            field=models.JSONField(blank=True, default=dict, editable=False),
        ),
    ]
