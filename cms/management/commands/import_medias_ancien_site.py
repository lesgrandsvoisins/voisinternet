"""
Reprend les images et les documents de l'ancien site (old.lesgrandsvoisins.com) dans la médiathèque Wagtail d'ici, à
partir de la liste de l'export (`tools/export_ancien_site.py`, lignes « image » et « document » de contenu.jsonl) et des
fichiers copiés dans MEDIA_ROOT/old-import/ (sous-dossiers original_images/ et documents/).

    manage.py import_medias_ancien_site /chemin/contenu.jsonl [--dossier MEDIA_ROOT/old-import]

Idempotent : un fichier déjà repris (même titre et même nom de fichier) est laissé tel quel. Les images vectorielles (SVG)
ne sont pas gérées par la médiathèque : elles sont signalées, pas reprises. Ensuite, `import_ancien_association --refaire`
place les images dans les pages et `reecrire_liens` remplace les liens vers les anciens documents.
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from wagtail.documents import get_document_model
from wagtail.images import get_image_model

RASTER = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def index_fichiers(racine):
    """Nom de fichier -> chemin, dans tout le dossier (les sous-dossiers de dates de Wagtail sont ignorés)."""
    return {p.name: p for p in sorted(Path(racine).rglob("*")) if p.is_file()}


class Command(BaseCommand):
    help = "Reprend les images et documents de l'ancien site dans la médiathèque Wagtail."

    def add_arguments(self, parser):
        parser.add_argument("export", help="contenu.jsonl produit par tools/export_ancien_site.py")
        parser.add_argument("--dossier", default=str(Path(settings.MEDIA_ROOT) / "old-import"))

    def handle(self, *args, export, dossier, **options):
        chemin = Path(export)
        if not chemin.is_file():
            raise CommandError(f"Fichier introuvable : {chemin}")
        racine = Path(dossier)
        if not racine.is_dir():
            raise CommandError(f"Dossier introuvable : {racine}")
        lignes = [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]
        fichiers_images = index_fichiers(racine / "original_images")
        fichiers_docs = index_fichiers(racine / "documents")
        Image, Document = get_image_model(), get_document_model()
        stats = {"images": 0, "documents": 0, "deja": 0, "svg": [], "absents": [], "erreurs": []}

        for e in (l for l in lignes if l.get("type") == "image"):
            nom = e["fichier"]
            if Path(nom).suffix.lower() not in RASTER:
                stats["svg"].append(nom)
                continue
            source = fichiers_images.get(nom)
            if source is None:
                stats["absents"].append(f"image {nom}")
                continue
            if Image.objects.filter(title=e["titre"] or nom, file__endswith=nom).exists():
                stats["deja"] += 1
                continue
            try:
                with open(source, "rb") as f:
                    Image.objects.create(title=e["titre"] or nom, file=File(f, name=nom))
                stats["images"] += 1
            except Exception as exc:  # un fichier illisible ne doit pas arrêter la reprise des autres
                stats["erreurs"].append(f"{nom} : {exc}")

        for e in (l for l in lignes if l.get("type") == "document"):
            nom = e["fichier"]
            source = fichiers_docs.get(nom)
            if source is None:
                stats["absents"].append(f"document {nom}")
                continue
            if Document.objects.filter(title=e["titre"] or nom, file__endswith=nom).exists():
                stats["deja"] += 1
                continue
            try:
                with open(source, "rb") as f:
                    Document.objects.create(title=e["titre"] or nom, file=File(f, name=nom))
                stats["documents"] += 1
            except Exception as exc:
                stats["erreurs"].append(f"{nom} : {exc}")

        self.stdout.write(self.style.SUCCESS(
            f"{stats['images']} image(s) et {stats['documents']} document(s) repris, {stats['deja']} déjà présent(s)."))
        for cle, titre in (("svg", "Images vectorielles non reprises"), ("absents", "Fichiers absents du dossier"),
                           ("erreurs", "Erreurs")):
            if stats[cle]:
                self.stdout.write(f"{titre} ({len(stats[cle])}) :")
                for x in stats[cle]:
                    self.stdout.write(f"  {x}")
