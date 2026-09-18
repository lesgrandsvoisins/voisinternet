"""
Importe en masse, comme wagtail.images.models.Image / wagtail.documents.models.Document
de ce site, les fichiers médias de l'ancien site wagtail_village (lesgrandsvoisins.com)
référencés par l'export de transition sites-faciles (workshop/qmd_export/export_transition_qmd.py)
— repérés par les marqueurs `legacy-image:<id>`/`legacy-document:<id>` laissés dans les .qmd
exportés (--qmd-dir), résolus en chemin de fichier via le dumpdata JSON d'origine (--dump,
wagtailimages.image/wagtaildocs.document), les fichiers eux-mêmes venant de --media-root.

N'importe que ce qui est réellement référencé (pas tout le dump), pour ne pas polluer la
médiathèque de contenu jamais migré.

Idempotent : écrit/relit un fichier de correspondance JSON {"images": {legacy_id: nouveau
pk}, "documents": {...}} (--map) — un legacy_id déjà présent (et dont l'objet existe encore)
est laissé tel quel plutôt que réimporté en double. Ce fichier sert aussi de pont pour une
future étape d'import de contenu : elle pourra y résoudre un marqueur legacy-image:<id>/
legacy-document:<id> vers le nouveau pk Wagtail de ce site.
"""
import json
import re
from pathlib import Path

from django.core.files import File
from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand, CommandError

_LEGACY_IMAGE_RE = re.compile(r"legacy-image:(\d+)")
_LEGACY_DOCUMENT_RE = re.compile(r"legacy-document:(\d+)")


def _scan_references(qmd_dir):
    images, documents = set(), set()
    for path in qmd_dir.rglob("*.qmd"):
        text = path.read_text(encoding="utf-8")
        images.update(int(m) for m in _LEGACY_IMAGE_RE.findall(text))
        documents.update(int(m) for m in _LEGACY_DOCUMENT_RE.findall(text))
    return images, documents


class Command(BaseCommand):
    help = "Importe en masse les images/documents legacy référencés par l'export sites-faciles."

    def add_arguments(self, parser):
        parser.add_argument("--dump", required=True, help="dumpdata JSON d'origine (wagtailimages.image/wagtaildocs.document).")
        parser.add_argument("--media-root", required=True, help="Racine des fichiers médias legacy (original_images/, documents/…).")
        parser.add_argument("--qmd-dir", required=True, help="Dossier .qmd exporté à scanner pour les marqueurs legacy-image:/legacy-document:.")
        parser.add_argument("--map", default="var/legacy_media_map.json", help="Fichier de correspondance legacy_id -> nouveau pk (créé/mis à jour).")

    def handle(self, *args, **options):
        from wagtail.documents.models import Document
        from wagtail.images.models import Image

        dump_path = Path(options["dump"])
        media_root = Path(options["media_root"])
        qmd_dir = Path(options["qmd_dir"])
        map_path = Path(options["map"])

        for label, path, is_dir in (
            ("dump", dump_path, False), ("media-root", media_root, True), ("qmd-dir", qmd_dir, True),
        ):
            if is_dir and not path.is_dir():
                raise CommandError(f"--{label} introuvable ou n'est pas un dossier : {path}")
            if not is_dir and not path.is_file():
                raise CommandError(f"--{label} introuvable : {path}")

        referenced_images, referenced_documents = _scan_references(qmd_dir)
        self.stdout.write(f"{len(referenced_images)} images et {len(referenced_documents)} documents référencés sous {qmd_dir}")

        dump = json.loads(dump_path.read_text(encoding="utf-8"))
        images_by_id = {obj["pk"]: obj["fields"] for obj in dump if obj["model"] == "wagtailimages.image"}
        documents_by_id = {obj["pk"]: obj["fields"] for obj in dump if obj["model"] == "wagtaildocs.document"}

        mapping = json.loads(map_path.read_text(encoding="utf-8")) if map_path.is_file() else {}
        mapping.setdefault("images", {})
        mapping.setdefault("documents", {})

        img_created, img_skipped, img_missing = self._import_batch(
            referenced_images, images_by_id, media_root, mapping["images"], Image, ImageFile,
        )
        doc_created, doc_skipped, doc_missing = self._import_batch(
            referenced_documents, documents_by_id, media_root, mapping["documents"], Document, File,
        )

        map_path.parent.mkdir(parents=True, exist_ok=True)
        map_path.write_text(json.dumps(mapping, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")

        self.stdout.write(self.style.SUCCESS(
            f"images : {img_created} créées, {img_skipped} déjà présentes, {img_missing} introuvables\n"
            f"documents : {doc_created} créés, {doc_skipped} déjà présents, {doc_missing} introuvables\n"
            f"correspondance écrite dans {map_path}"
        ))

    def _import_batch(self, legacy_ids, fields_by_id, media_root, id_map, model, file_wrapper):
        created = skipped = missing = 0
        for legacy_id in sorted(legacy_ids):
            key = str(legacy_id)
            existing_pk = id_map.get(key)
            if existing_pk and model.objects.filter(pk=existing_pk).exists():
                skipped += 1
                continue

            fields = fields_by_id.get(legacy_id)
            if not fields or not fields.get("file"):
                self.stderr.write(f"{model.__name__.lower()} legacy {legacy_id} : absent du dump ou sans fichier")
                missing += 1
                continue

            file_path = media_root / fields["file"]
            if not file_path.is_file():
                self.stderr.write(f"{model.__name__.lower()} legacy {legacy_id} : fichier introuvable ({file_path})")
                missing += 1
                continue

            with open(file_path, "rb") as f:
                obj = model.objects.create(
                    title=fields.get("title") or file_path.name,
                    file=file_wrapper(f, name=file_path.name),
                )
            id_map[key] = obj.pk
            created += 1
        return created, skipped, missing
