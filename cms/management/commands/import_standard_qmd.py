"""Importe ou met à jour une page générique depuis un fichier .qmd — voir cms/qmd.py."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from cms.qmd import import_standardpage_qmd


class Command(BaseCommand):
    help = "Importe ou met à jour une page générique (cms.StandardPage) depuis un fichier .qmd."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Chemin du fichier .qmd à importer.")

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.is_file():
            raise CommandError(f"Fichier introuvable : {path}")

        page = import_standardpage_qmd(path.read_text(encoding="utf-8"))
        self.stdout.write(self.style.SUCCESS(f"importé : {page.full_url} (clé {page.translation_key})"))
