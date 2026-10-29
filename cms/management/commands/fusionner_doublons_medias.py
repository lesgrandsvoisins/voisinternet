"""
Supprime les copies INUTILISÉES des images et documents en double (même contenu : même empreinte de fichier). Pour chaque
groupe de copies identiques, on garde celle qui sert le plus (à égalité, la plus ancienne) et on ne supprime que les autres
copies que ni une page ni un autre objet n'utilise. Une copie utilisée est laissée en place et signalée.

    manage.py fusionner_doublons_medias              # simulation : rapport seulement
    manage.py fusionner_doublons_medias --appliquer  # supprime

Des images de même titre mais de contenu différent (ex. `logo.png` et `logo.svg`) ne sont PAS des doublons : intactes.
Sauvegarde recommandée avant --appliquer (les fichiers supprimés ne reviennent pas).
"""
import hashlib
from collections import defaultdict

from django.core.management.base import BaseCommand
from wagtail.documents import get_document_model
from wagtail.images import get_image_model
from wagtail.models import ReferenceIndex


def empreinte(objet):
    if getattr(objet, "file_hash", ""):
        return objet.file_hash
    try:
        h = hashlib.sha1()
        with objet.file.open("rb") as f:
            for bloc in iter(lambda: f.read(1024 * 1024), b""):
                h.update(bloc)
        return h.hexdigest()
    except OSError:
        return ""


def usages(objet):
    return ReferenceIndex.get_references_to(objet).count()


class Command(BaseCommand):
    help = "Supprime les copies inutilisées d'images et de documents identiques."

    def add_arguments(self, parser):
        parser.add_argument("--appliquer", action="store_true", help="Supprimer (sinon simulation)")

    def handle(self, *args, appliquer, **options):
        total_supprimes = total_gardes_utilises = 0
        for modele in (get_image_model(), get_document_model()):
            groupes = defaultdict(list)
            for o in modele.objects.order_by("pk"):
                h = empreinte(o)
                if h:
                    groupes[h].append(o)
            self.stdout.write(f"== {modele.__name__} : {sum(1 for g in groupes.values() if len(g) > 1)} groupe(s) de doublons")
            for copies in (g for g in groupes.values() if len(g) > 1):
                mesure = [(usages(o), o) for o in copies]
                garde = sorted(mesure, key=lambda t: (-t[0], t[1].pk))[0][1]
                for n, o in mesure:
                    if o.pk == garde.pk:
                        continue
                    if n:
                        total_gardes_utilises += 1
                        self.stdout.write(f"  gardée (utilisée {n}×) : #{o.pk} {o.title!r} (double de #{garde.pk})")
                        continue
                    total_supprimes += 1
                    self.stdout.write(f"  {'supprimée' if appliquer else 'à supprimer'} : #{o.pk} {o.title!r} (double de #{garde.pk})")
                    if appliquer:
                        o.delete()
        self.stdout.write(self.style.SUCCESS(
            f"{total_supprimes} copie(s) inutilisée(s) {'supprimée(s)' if appliquer else 'à supprimer (--appliquer)'} ; "
            f"{total_gardes_utilises} copie(s) en double mais utilisée(s), laissée(s)."))
