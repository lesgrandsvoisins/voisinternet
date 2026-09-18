"""Exporte une page générique (cms.StandardPage) au format .qmd — voir cms/qmd.py."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from cms.models import StandardPage
from cms.qmd import export_standardpage_qmd


class Command(BaseCommand):
    help = "Exporte une page générique (identifiée par son slug et sa langue) en fichier .qmd."

    def add_arguments(self, parser):
        parser.add_argument("slug", help="Slug de la page (cms.StandardPage.slug).")
        parser.add_argument("--lang", default="fr", help="Langue de la page à exporter (défaut : fr).")
        parser.add_argument("--out", help="Chemin du fichier .qmd à écrire (défaut : <slug>.qmd).")

    def handle(self, *args, **options):
        page = StandardPage.objects.filter(slug=options["slug"], locale__language_code=options["lang"]).first()
        if page is None:
            raise CommandError(f"Aucune page « {options['slug']} » en langue « {options['lang']} ».")

        out_path = Path(options["out"] or f"{page.slug}.qmd")
        out_path.write_text(export_standardpage_qmd(page), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"exporté : {out_path}"))
