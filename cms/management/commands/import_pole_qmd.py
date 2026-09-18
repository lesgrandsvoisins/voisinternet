"""Met à jour les cartes d'un pôle depuis un fichier .qmd — voir cms/qmd.py."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from cms.qmd import import_polepage_qmd


class Command(BaseCommand):
    help = "Met à jour les cartes d'un pôle existant (cms.PolePage.cards) depuis un fichier .qmd."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Chemin du fichier .qmd à importer.")

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.is_file():
            raise CommandError(f"Fichier introuvable : {path}")

        page = import_polepage_qmd(path.read_text(encoding="utf-8"))
        self.stdout.write(self.style.SUCCESS(f"importé : {page.full_url} (clé {page.translation_key})"))
