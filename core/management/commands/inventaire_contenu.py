"""
Inventaire du contenu public pour la revue éditoriale : une ligne par page Wagtail, évènement, fiche d'annuaire et service,
avec des alertes à vérifier (brouillon, texte vide, image de une ou description manquante, titre en double, liens vers
les anciens sites, images sans texte alternatif, traductions manquantes). Lecture seule.

    manage.py inventaire_contenu [--sortie /tmp/revue] [--liens]

Produit dans le dossier de sortie :
  - inventaire.csv : à ouvrir dans un tableur ; colonnes « décision » et « remarque » vides, pour les relecteurs ;
  - resume.md      : décompte par alerte, avec les premiers exemples.
--liens vérifie aussi que chaque lien interne répond (plus long). Aucune donnée personnelle : pas de courriel ni de
téléphone, et les fiches d'annuaire non publiques sont signalées sans leur contenu.
"""
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand
from django.test import Client

HOTES_ANCIENS = re.compile(r"https?://(?:old2?|blog)\.lesgrandsvoisins\.(?:com|fr)|https?://(?:www\.)?lesgrandsvoisins\.(?:fr|org)\b")
TYPES_AVEC_IMAGE_DE_UNE = ("BlogPostPage", "ProjectPage", "PolePage")


def texte_brut(valeur):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", valeur or "")).strip()


class Command(BaseCommand):
    help = "Inventaire du contenu public pour la revue éditoriale (CSV + résumé)."

    def add_arguments(self, parser):
        parser.add_argument("--sortie", default="revue-contenu")
        parser.add_argument("--liens", action="store_true", help="Vérifier que les liens internes répondent")

    def handle(self, *args, sortie, liens, **options):
        from wagtail.models import Page

        dossier = Path(sortie)
        dossier.mkdir(parents=True, exist_ok=True)
        lignes = []
        titres = defaultdict(list)

        for page in Page.objects.exclude(depth=1).order_by("path").specific():
            donnees = json.dumps(page.serializable_data(), ensure_ascii=False, default=str)
            brut = donnees.replace('\\"', '"').replace("\\/", "/")
            texte = texte_brut(re.sub(r'\\u003c', '<', brut))
            embeds = re.findall(r"<embed[^>]*embedtype=\"image\"[^>]*/?>", brut)
            sans_alt = sum(1 for e in embeds if re.search(r'alt=""', e) or "alt=" not in e)
            href = re.findall(r'href="([^"]+)"', brut)
            anciens = [h for h in href if HOTES_ANCIENS.match(h)]
            internes = [h for h in href if h.startswith("/")]
            type_page = page._meta.object_name
            statut = "publié" if page.live else "brouillon"
            traductions = Page.objects.filter(translation_key=page.translation_key).exclude(pk=page.pk).count()
            ligne = {
                "type": type_page, "titre": page.title, "adresse": page.url_path, "langue": getattr(page.locale, "language_code", ""),
                "statut": statut, "date": str(getattr(page, "date", "") or page.first_published_at or "")[:10],
                "modifiée": str(page.latest_revision_created_at or "")[:10], "texte": len(texte), "images": len(embeds),
                "traductions": f"{traductions}/4" if page.locale.language_code == "fr" else "",
                "liens_anciens": len(anciens), "décision": "", "remarque": "",
            }
            alertes = []
            if not page.live:
                alertes.append("brouillon")
            if len(texte) < 150 and type_page not in ("HomePage",):
                alertes.append("texte-court")
            if type_page in TYPES_AVEC_IMAGE_DE_UNE and not getattr(page, "featured_image_id", None):
                alertes.append("sans-image-de-une")
            if not page.search_description and page.live:
                alertes.append("sans-description")
            if anciens:
                alertes.append("lien-ancien-site")
            if sans_alt:
                alertes.append("image-sans-texte-alternatif")
            if page.locale.language_code == "fr" and traductions < 4 and type_page in ("PolePage", "AssociationPage", "ProjectPage", "BlogIndexPage"):
                alertes.append("traductions-manquantes")
            ligne["_liens"] = internes
            ligne["_alertes"] = alertes
            lignes.append(ligne)
            if page.live:
                titres[(page.locale_id, page.title.strip().lower())].append(ligne)

        for groupe in titres.values():
            if len(groupe) > 1:
                for l in groupe:
                    l["_alertes"].append("titre-en-double")

        from core.models import DirectoryEntry, Event, Service
        for e in Event.objects.order_by("-start"):
            lignes.append({"type": "Évènement", "titre": e.title, "adresse": f"/agenda/{e.pk}/", "langue": "fr",
                           "statut": "publié" if e.public else "non publié", "date": str(e.start)[:10], "modifiée": "",
                           "texte": len(texte_brut(e.description)), "images": 1 if e.photo else 0, "traductions": "",
                           "liens_anciens": 0, "décision": "", "remarque": "", "_liens": [],
                           "_alertes": ([] if e.public else ["non-publié"]) + ([] if e.photo else ["sans-image-de-une"])})
        for d in DirectoryEntry.objects.order_by("name"):
            publique = d.visibility == "public" if hasattr(d, "visibility") else True
            lignes.append({"type": "Fiche d'annuaire", "titre": d.name, "adresse": f"/annuaire/{d.slug}/", "langue": "fr",
                           "statut": "publiée" if publique and d.approved else "non publique", "date": "", "modifiée": "",
                           "texte": len(texte_brut(d.description)), "images": 0, "traductions": "", "liens_anciens": 0,
                           "décision": "", "remarque": "", "_liens": [],
                           "_alertes": ([] if publique and d.approved else ["non-publique"]) + (["texte-court"] if len(texte_brut(d.description)) < 80 else [])})
        for s in Service.objects.order_by("order", "name"):
            lignes.append({"type": "Service", "titre": s.name, "adresse": s.url, "langue": "fr", "statut": "proposé" if s.active else "retiré",
                           "date": "", "modifiée": "", "texte": len(texte_brut(s.description)), "images": 0, "traductions": "",
                           "liens_anciens": 1 if HOTES_ANCIENS.match(s.url or "") else 0, "décision": "", "remarque": "", "_liens": [],
                           "_alertes": ([] if s.url else ["sans-adresse"]) + ([] if s.active else ["retiré"])})

        if liens:
            client = Client()
            cache = {}
            for l in lignes:
                for h in set(l["_liens"]):
                    chemin = h.split("#")[0]
                    if chemin not in cache:
                        try:
                            cache[chemin] = client.get(chemin, HTTP_HOST="localhost").status_code
                        except Exception:
                            cache[chemin] = 500
                    if cache[chemin] >= 400 and cache[chemin] != 403:
                        l["_alertes"].append(f"lien-interne-cassé({chemin})")

        colonnes = ["type", "titre", "adresse", "langue", "statut", "date", "modifiée", "texte", "images", "traductions",
                    "liens_anciens", "alertes", "décision", "remarque"]
        with open(dossier / "inventaire.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=colonnes, extrasaction="ignore")
            w.writeheader()
            for l in lignes:
                l["alertes"] = " ; ".join(l["_alertes"])
                w.writerow(l)

        compte = Counter(a.split("(")[0] for l in lignes for a in l["_alertes"])
        par_type = Counter(l["type"] for l in lignes)
        with open(dossier / "resume.md", "w", encoding="utf-8") as f:
            f.write(f"# Revue de contenu : résumé\n\n{len(lignes)} éléments.\n\n## Par type\n\n")
            for t, n in par_type.most_common():
                f.write(f"- {t} : {n}\n")
            f.write("\n## Alertes\n\n")
            for a, n in compte.most_common():
                exemples = [l["titre"] for l in lignes if any(x.startswith(a) for x in l["_alertes"])][:6]
                f.write(f"- **{a}** : {n} — ex. {', '.join(exemples)}\n")
        self.stdout.write(self.style.SUCCESS(f"{len(lignes)} éléments → {dossier}/inventaire.csv et resume.md"))
        for a, n in compte.most_common():
            self.stdout.write(f"  {n:4d}  {a}")
