"""
Prépare le catalogue des services pour la page publique « Tous les outils » (/fr/outils/), qui remplace le tableau de
bord Homepage de www.gv.je :

  - Vikunja : l'adresse mène directement à la page de connexion ;
  - Keycloak, ListMonk, SftpGo, Ghost (administration) : « réservé à l'administration » (visibles du groupe
    « Administration » seulement) ;
  - Immich (photos) : ajouté s'il manque.

    manage.py preparer_catalogue_outils               # simulation : rapport seulement
    manage.py preparer_catalogue_outils --appliquer   # écrit

Ne retire rien, ne touche ni aux catégories, ni à l'ordre, ni aux autres champs choisis dans /admin/. Idempotent.
"""
from django.core.management.base import BaseCommand
from django.db.models import Max
from django.utils import translation

from core.models import Service

ADRESSES = {"vikunja": "https://vikunja.gv.je/login"}
ADMINISTRATION = ["keycloak", "listmonk", "sftpgo", "ghost"]
A_CREER = [{
    "slug": "immich", "name": "Immich", "url": "https://immich.gv.je",
    "summary": "Photos et vidéos partagées, hébergées par l'association.",
}]


class Command(BaseCommand):
    help = "Prépare le catalogue des services pour la page « Tous les outils »."

    def add_arguments(self, parser):
        parser.add_argument("--appliquer", action="store_true", help="écrit (sans cela : simulation)")

    def handle(self, *args, appliquer=False, **options):
        faits = 0
        with translation.override("fr"):
            for slug, url in ADRESSES.items():
                s = Service.objects.filter(slug=slug).first()
                if s is None:
                    self.stdout.write(f"  absent : {slug} (adresse non posée)")
                elif s.url != url:
                    self.stdout.write(f"  adresse de {s.name} : {s.url or '(vide)'} -> {url}")
                    faits += 1
                    if appliquer:
                        s.url = url
                        s.save(update_fields=["url"])
            for slug in ADMINISTRATION:
                s = Service.objects.filter(slug=slug).first()
                if s is None:
                    self.stdout.write(f"  absent : {slug} (à marquer à la main)")
                elif not s.administration_only:
                    self.stdout.write(f"  {s.name} : réservé à l'administration")
                    faits += 1
                    if appliquer:
                        s.administration_only = True
                        s.save(update_fields=["administration_only"])
            for spec in A_CREER:
                if Service.objects.filter(slug=spec["slug"]).exists():
                    continue
                self.stdout.write(f"  ajout : {spec['name']} ({spec['url']})")
                faits += 1
                if appliquer:
                    ordre = (Service.objects.aggregate(m=Max("order"))["m"] or 0) + 1
                    Service.objects.create(order=ordre, active=True, **spec)
        if not faits:
            self.stdout.write("Catalogue déjà prêt : rien à faire.")
        elif appliquer:
            self.stdout.write(f"{faits} changement(s) appliqué(s).")
        else:
            self.stdout.write(f"Simulation : {faits} changement(s) à faire (--appliquer pour écrire).")
