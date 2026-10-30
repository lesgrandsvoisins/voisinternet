"""
Supprime les comptes ANONYMES inutilisés : ni service, ni groupe, ni fiche, ni don, ni évènement, ni aucune autre donnée
rattachée, et pas vus depuis N jours (30 par défaut). Ne touche jamais un compte nommé (connecté par Keycloak), ni un compte
anonyme qui a la moindre donnée, ni un compte anonyme récent (la personne n'a peut-être pas encore noté son numéro).

    manage.py purger_comptes_anonymes                  # simulation : rapport seulement
    manage.py purger_comptes_anonymes --jours 60       # autre durée d'inactivité
    manage.py purger_comptes_anonymes --appliquer      # supprime

Contexte : « Mes fiches » créait un compte anonyme à chaque passage (robots compris) avant la correction du 28/10 : près de
2 000 comptes vides. Sauvegarde recommandée avant --appliquer (deploy/sauvegarde.sh). Idempotent.
"""
from collections import Counter
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Account


def relations_inverses():
    """Relations qui pointent VERS un compte (services, groupes, fiches, dons…), y compris les relations cachées."""
    return [f for f in Account._meta.get_fields(include_hidden=True)
            if (f.one_to_many or f.one_to_one) and f.auto_created and not f.concrete]


class Command(BaseCommand):
    help = "Supprime les comptes anonymes inutilisés (sans donnée, inactifs depuis N jours)."

    def add_arguments(self, parser):
        parser.add_argument("--jours", type=int, default=30, help="Inactivité minimale en jours (défaut : 30)")
        parser.add_argument("--appliquer", action="store_true", help="Supprimer (sinon simulation)")

    def handle(self, *args, jours, appliquer, **options):
        limite = timezone.now() - timedelta(days=jours)
        anonymes = dict(Account.objects.filter(user__isnull=True).values_list("pk", "last_seen"))
        protege = {}  # pk -> raison
        for pk, vu in anonymes.items():
            if vu and vu > limite:
                protege[pk] = f"vu depuis moins de {jours} jours"
        ids = set(anonymes)
        for rel in relations_inverses():
            champ = rel.field.attname  # colonne qui pointe vers le compte
            avec = set(rel.related_model._base_manager.filter(**{f"{champ}__in": ids}).values_list(champ, flat=True))
            for pk in avec:
                protege.setdefault(pk, f"a des données : {rel.related_model._meta.label}")
        a_supprimer = sorted(ids - set(protege))
        raisons = Counter(r.split(" :")[0] if r.startswith("a des") else r for r in protege.values())
        detail = Counter(r for r in protege.values() if r.startswith("a des"))

        self.stdout.write(f"Comptes anonymes : {len(ids)} ; comptes nommés non concernés.")
        self.stdout.write(f"  gardés : {len(protege)}")
        for r, n in raisons.most_common():
            self.stdout.write(f"    {n:5d}  {r}")
        for r, n in detail.most_common():
            self.stdout.write(f"             {n:5d}  {r}")
        self.stdout.write(f"  {'supprimés' if appliquer else 'à supprimer'} : {len(a_supprimer)} (vides, inactifs depuis plus de {jours} jours)")
        if appliquer and a_supprimer:
            for i in range(0, len(a_supprimer), 500):
                Account.objects.filter(pk__in=a_supprimer[i:i + 500], user__isnull=True).delete()
            self.stdout.write(self.style.SUCCESS(f"{len(a_supprimer)} compte(s) anonyme(s) supprimé(s)."))
        elif a_supprimer:
            self.stdout.write("Simulation : rien n'a été supprimé (--appliquer pour supprimer).")
