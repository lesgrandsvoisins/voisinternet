"""Importe ou met à jour un évènement de l'agenda depuis un fichier .qmd — voir core/qmd.py."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.qmd import import_event_qmd


class Command(BaseCommand):
    help = "Importe ou met à jour un évènement de l'agenda (core.Event) depuis un fichier .qmd."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Chemin du fichier .qmd à importer.")

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.is_file():
            raise CommandError(f"Fichier introuvable : {path}")

        event = import_event_qmd(path.read_text(encoding="utf-8"))
        self.stdout.write(self.style.SUCCESS(f"importé : {event.title} (pk {event.pk}, uid {event.source_uid})"))
