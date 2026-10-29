"""
Réécrit, dans tout le contenu du site, les liens absolus vers l'ancien site (old.lesgrandsvoisins.com) et vers le blog
Ghost (blog.lesgrandsvoisins.com) quand la page équivalente existe ICI. Un lien sans équivalent exact n'est jamais
modifié (il serait vidé de son sens) : il est listé dans le rapport, pour être traité à la reprise du contenu.

    manage.py reecrire_liens              # simulation : rapport seulement
    manage.py reecrire_liens --appliquer  # écrit (pages, révisions Wagtail, services, fiches, évènements…)

Une sauvegarde de la base avant `--appliquer` est de rigueur (deploy/sauvegarde.sh). Idempotent.
"""
import json
import re
from collections import Counter, defaultdict
from urllib.parse import quote, unquote, urlsplit

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.db.models import TextField
from django.db.models.functions import Cast

from core.legacy import equivalent_ancien_site, equivalent_blog

APPLIS = ("cms", "core", "wagtailcore")
TYPES = {"TextField", "CharField", "URLField", "JSONField"}
# Champs qui DÉSIGNENT l'ancien site ou Ghost (annuaire des services : « le blog », « l'ancien site ») : jamais réécrits.
EXCLUS = {"core.Service.url"}
FIN = r"""[^\s"'\\<>)\]]*"""
RE_OLD = re.compile(r"https?://(?:old2?)\.lesgrandsvoisins\.(?:com|fr)(?P<path>/" + FIN + r")?")
RE_BLOG = re.compile(r"https?://blog\.lesgrandsvoisins\.(?:com|fr)(?P<path>/" + FIN + r")?")
LANGUES_VIEUX_SITE = {"fr-fr", "fr"}


def cible_document(parts):
    """/documents/<id>/<fichier> de l'ancien site -> adresse du même fichier repris dans les documents d'ici."""
    from wagtail.documents import get_document_model

    doc = get_document_model().objects.filter(file__endswith=parts[-1]).first()
    return doc.url if doc else None


def cible_vieux_site(chemin):
    parts = [p for p in unquote(urlsplit(chemin or "/").path).split("/") if p]
    if len(parts) == 3 and parts[0] == "documents":
        return cible_document(parts)
    if parts and parts[0].lower() in LANGUES_VIEUX_SITE:
        parts = parts[1:]
    elif parts:
        return None  # autre langue ou autre arborescence : à traiter à la main
    return equivalent_ancien_site(parts, exact=True)


def cible_blog(chemin):
    from core.models import Tag

    parts = [p for p in unquote(urlsplit(chemin or "/").path).split("/") if p]
    if not parts:
        return "/fr/blog/"
    if len(parts) == 2 and parts[0] == "tag":
        if Tag.objects.filter(slug=parts[1]).exists():
            return f"/fr/etiquettes/{parts[1]}/"
        # Pas d'étiquette de ce nom ici : la recherche du site donne ce que listait la page d'étiquette de Ghost.
        return f"/fr/recherche/?q={quote(parts[1])}"
    if len(parts) == 1 and parts[0] not in {"ghost", "tag", "author", "rss", "content"}:
        return equivalent_blog(parts[0])
    return None


class Command(BaseCommand):
    help = "Réécrit les liens vers l'ancien site et le blog Ghost quand la page équivalente existe ici."

    def add_arguments(self, parser):
        parser.add_argument("--appliquer", action="store_true", help="Écrire les changements (sinon simulation)")

    def handle(self, *args, appliquer, **options):
        self.reecrits = Counter()
        self.restes = defaultdict(Counter)  # URL non réécrite -> {modèle.champ: occurrences}
        total = 0
        with transaction.atomic():
            for model in apps.get_models():
                if model._meta.app_label not in APPLIS or model._meta.proxy or not model._meta.managed:
                    continue
                for field in model._meta.concrete_fields:
                    if field.primary_key or field.is_relation or field.get_internal_type() not in TYPES:
                        continue
                    if f"{model._meta.label}.{field.name}" in EXCLUS:
                        continue
                    total += self.traiter(model, field, appliquer)
        mode = "réécrits" if appliquer else "à réécrire (simulation, --appliquer pour écrire)"
        self.stdout.write(f"\n{sum(self.reecrits.values())} lien(s) {mode} :")
        for k, n in sorted(self.reecrits.items()):
            self.stdout.write(f"  {n:4d}  {k}")
        if self.restes:
            self.stdout.write(f"\n{len(self.restes)} adresse(s) sans équivalent ici, laissées telles quelles :")
            for url, ou in sorted(self.restes.items()):
                self.stdout.write(f"  {sum(ou.values()):3d}×  {url}   ({', '.join(sorted(ou))})")

    def traiter(self, model, field, appliquer):
        nom = f"{model._meta.label}.{field.name}"
        qs = model._base_manager.annotate(_texte=Cast(field.name, TextField())).filter(_texte__contains="lesgrandsvoisins.")
        n = 0
        for pk, texte in qs.values_list("pk", "_texte"):
            nouveau = self.remplacer(texte, nom)
            if nouveau == texte:
                continue
            n += 1
            if appliquer:
                self.ecrire(model, field, pk, nouveau)
        return n

    def remplacer(self, texte, nom):
        def sub(cible):
            def f(m):
                autre = cible(m.group("path"))
                if autre:
                    self.reecrits[nom] += 1
                    return autre
                self.restes[m.group(0)][nom] += 1
                return m.group(0)
            return f
        texte = RE_OLD.sub(sub(cible_vieux_site), texte)
        return RE_BLOG.sub(sub(cible_blog), texte)

    def ecrire(self, model, field, pk, nouveau):
        if field.get_internal_type() == "JSONField":
            # Texte JSON réécrit tel quel (StreamField compris) : on ne repasse pas par le champ pour ne rien reformater.
            json.loads(nouveau)  # refuse d'écrire un JSON invalide
            with connection.cursor() as cur:
                cur.execute(
                    f'UPDATE "{model._meta.db_table}" SET "{field.column}" = %s WHERE "{model._meta.pk.column}" = %s',
                    [nouveau, pk],
                )
        else:
            model._base_manager.filter(pk=pk).update(**{field.name: nouveau})
