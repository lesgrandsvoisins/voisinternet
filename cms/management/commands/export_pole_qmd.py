"""Exporte un pôle (cms.PolePage) au format .qmd — voir cms/qmd.py."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from cms.models import PolePage
from cms.qmd import export_polepage_qmd


class Command(BaseCommand):
    help = "Exporte un pôle (identifié par son slug et sa langue) en fichier .qmd."

    def add_arguments(self, parser):
        parser.add_argument("slug", help="Slug du pôle (cms.PolePage.slug).")
        parser.add_argument("--lang", default="fr", help="Langue du pôle à exporter (défaut : fr).")
        parser.add_argument("--out", help="Chemin du fichier .qmd à écrire (défaut : <slug>.qmd).")

    def handle(self, *args, **options):
        page = PolePage.objects.filter(slug=options["slug"], locale__language_code=options["lang"]).first()
        if page is None:
            raise CommandError(f"Aucun pôle « {options['slug']} » en langue « {options['lang']} ».")

        out_path = Path(options["out"] or f"{page.slug}.qmd")
        out_path.write_text(export_polepage_qmd(page), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"exporté : {out_path}"))
