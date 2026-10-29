"""
Complète les images d'en-tête manquantes (jamais celles déjà posées) :

  - billets et pages du blog repris de Ghost (`featured_image`), d'après le champ feature_image de l'export Ghost ;
  - pages de la section Association reprises de l'ancien site (`header_image`), d'après l'export de l'ancien site.

    manage.py completer_images_entetes [--ghost export.json] [--ancien contenu.jsonl] [--dossier D …]

Les fichiers sont cherchés dans les --dossier donnés (par défaut deploy/ghost-export, MEDIA_ROOT/ghost-content,
MEDIA_ROOT/ghost-import, MEDIA_ROOT/old-import) : d'abord au chemin relatif de l'image (images/2023/05/x.jpg), puis par
nom de fichier. Une image déjà dans la médiathèque est réutilisée. Idempotent ; simulation avec --simulation.
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from wagtail.images import get_image_model
from wagtail.models import Locale

from cms.models import AssociationPage, BlogPostPage, StandardPage


class Command(BaseCommand):
    help = "Complète les images d'en-tête manquantes des billets du blog et des pages Association."

    def add_arguments(self, parser):
        parser.add_argument("--ghost", help="Export JSON de Ghost")
        parser.add_argument("--ancien", help="contenu.jsonl de l'ancien site (tools/export_ancien_site.py)")
        parser.add_argument("--dossier", action="append", help="Dossier où chercher les fichiers (répétable)")
        parser.add_argument("--simulation", action="store_true")

    def handle(self, *args, ghost, ancien, dossier, simulation, **options):
        if not ghost and not ancien:
            raise CommandError("Donner --ghost et/ou --ancien.")
        media = Path(settings.MEDIA_ROOT)
        base = Path(settings.BASE_DIR)
        self.dossiers = [Path(d) for d in dossier] if dossier else [
            base / "deploy" / "ghost-export", media / "ghost-content", media / "ghost-import", media / "old-import"]
        self.simulation = simulation
        self.index = {}
        for d in self.dossiers:
            if d.is_dir():
                for p in d.rglob("*"):
                    if p.is_file():
                        self.index.setdefault(p.name, p)
        self.stats = {"posees": 0, "deja": 0, "absentes": []}
        if ghost:
            self.ghost(Path(ghost))
        if ancien:
            self.ancien(Path(ancien))
        self.stdout.write(self.style.SUCCESS(
            f"{self.stats['posees']} image(s) d'en-tête {'à poser' if simulation else 'posée(s)'}, "
            f"{self.stats['deja']} page(s) en avaient déjà une."))
        if self.stats["absentes"]:
            self.stdout.write(f"Fichiers introuvables ({len(self.stats['absentes'])}) :")
            for x in self.stats["absentes"]:
                self.stdout.write(f"  {x}")

    def image(self, relatif):
        """Image de la médiathèque pour ce chemin ou nom de fichier ; la crée depuis les dossiers si besoin."""
        Image = get_image_model()
        nom = Path(relatif).name
        existante = Image.objects.filter(file__endswith=nom).first()
        if existante:
            return existante
        source = None
        for d in self.dossiers:
            candidat = d / relatif
            if candidat.is_file():
                source = candidat
                break
        source = source or self.index.get(nom)
        if source is None:
            return None
        if self.simulation:
            return True
        with open(source, "rb") as f:
            return Image.objects.create(title=Path(nom).stem, file=File(f, name=nom))

    def poser(self, page, champ, relatif, etiquette):
        if getattr(page, f"{champ}_id"):
            self.stats["deja"] += 1
            return
        image = self.image(relatif)
        if image is None:
            self.stats["absentes"].append(f"{etiquette} : {relatif}")
            return
        self.stats["posees"] += 1
        self.stdout.write(f"{etiquette} : {Path(relatif).name}")
        if self.simulation:
            return
        setattr(page, champ, image)
        revision = page.save_revision()
        if page.live:
            revision.publish()
        else:
            page.save()

    def ghost(self, chemin):
        data = json.loads(chemin.read_text(encoding="utf-8"))["db"][0]["data"]
        for p in data["posts"]:
            if p["status"] != "published" or not p.get("feature_image"):
                continue
            page = BlogPostPage.objects.filter(slug=p["slug"]).first()
            if page:
                self.poser(page, "featured_image", p["feature_image"].replace("__GHOST_URL__/content/", ""), f"blog/{p['slug']}")

    def ancien(self, chemin):
        lignes = [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]
        noms = {l["id"]: l["fichier"] for l in lignes if l.get("type") == "image"}
        racine = AssociationPage.objects.filter(locale=Locale.get_default()).first()
        prefixe = "/wwwlesgrandsvoisinscom/association/"
        for l in sorted((x for x in lignes if x.get("type") == "page" and x["url_path"].startswith(prefixe)
                         and x["url_path"] != prefixe), key=lambda x: x["url_path"]):
            ancien_id = l["contenu"].get("header_image")
            if not ancien_id or racine is None:
                continue
            page = racine
            for slug in l["url_path"][len(prefixe):].strip("/").split("/"):
                page = page.get_children().filter(slug=slug).first()
                if page is None:
                    break
            nom = noms.get(int(ancien_id))
            if page is not None and nom:
                self.poser(page.specific, "header_image", nom, f"association/{l['slug']}")
