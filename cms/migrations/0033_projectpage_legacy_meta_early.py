# Même besoin que 0032_polepage_legacy_meta_early.py, pour ProjectPage cette fois :
# cms.0019_pole_cards_to_projects crée de vraies ProjectPage (pole.add_child(instance=
# project), StreamField "body") via le modèle courant. ProjectPage n'existe qu'à partir
# de 0015 (créé dans la même migration que PolePage.tags) : dépendance directe sur 0015
# plutôt que sur 0005 (trop tôt, le modèle n'existe pas encore). 0019 doit dépendre de
# celle-ci en plus de 0018 (voir sa modification).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0015_blogpostpage_tags_polepage_tags_projectpage'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectpage',
            name='legacy_meta',
            field=models.JSONField(blank=True, default=dict, editable=False),
        ),
    ]
