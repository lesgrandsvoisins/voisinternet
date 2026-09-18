"""Exporte un évènement de l'agenda (identifié par son pk) en fichier .qmd — voir core/qmd.py."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.models import Event
from core.qmd import export_event_qmd


class Command(BaseCommand):
    help = "Exporte un évènement de l'agenda (identifié par son pk) en fichier .qmd."

    def add_arguments(self, parser):
        parser.add_argument("pk", type=int, help="Identifiant de l'évènement (core.Event.pk).")
        parser.add_argument("--out", help="Chemin du fichier .qmd à écrire (défaut : <slug>.qmd).")

    def handle(self, *args, **options):
        try:
            event = Event.objects.get(pk=options["pk"])
        except Event.DoesNotExist:
            raise CommandError(f"Aucun évènement avec l'identifiant {options['pk']}.")

        out_path = Path(options["out"] or f"{event.slug}.qmd")
        out_path.write_text(export_event_qmd(event), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"exporté : {out_path} (uid {event.source_uid})"))
