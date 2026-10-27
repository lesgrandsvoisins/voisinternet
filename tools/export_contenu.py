"""
Extrait le contenu PUBLIC d'un site Django/Wagtail en un fichier JSON Lines, pour comparer l'ancien et le
nouveau site (pages à reprendre, redirections à écrire). Lecture seule, rien n'est modifié.

Usage (depuis le dossier du projet, avec son environnement Python et ses variables d'environnement) :

    SORTIE=/tmp/contenu-old.jsonl .venv/bin/python manage.py shell < tools/export_contenu.py

Ce qui est extrait (une ligne JSON par élément, champ « type ») :
  - « wagtail_page »     : pages Wagtail publiées (arbre, titre, adresse, langue, dates, contenu des champs) ;
  - « wagtail_redirect » : redirections Wagtail (ancienne adresse -> nouvelle) ;
  - « event »            : évènements de l'agenda PUBLIÉS (sans responsables) ;
  - « directory_entry »  : fiches d'annuaire PUBLIQUES et validées, sans courriel, téléphone ni adresse précise ;
  - « service » / « audience » : données de configuration du site.
Jamais extraits : comptes, utilisateurs, mots de passe, messages, demandes, dons, brouillons, journaux.
Ce qui n'existe pas dans le site visé (par exemple « core » sur l'ancien site Wagtail) est simplement ignoré.
"""
import json
import os
from datetime import date, datetime

from django.db import DatabaseError, transaction

SORTIE = os.environ.get("SORTIE", "contenu.jsonl")
compte = {}


def ecrire(f, type_, data):
    f.write(json.dumps({"type": type_, **data}, ensure_ascii=False, default=str) + "\n")
    compte[type_] = compte.get(type_, 0) + 1


def champs(obj, exclure=()):
    """Champs simples d'un objet (valeurs sérialisables), sans les relations."""
    out = {}
    for champ in obj._meta.concrete_fields:
        if champ.name in exclure or champ.is_relation:
            continue
        valeur = getattr(obj, champ.attname)
        out[champ.name] = valeur.isoformat() if isinstance(valeur, (datetime, date)) else valeur
    return out


with open(SORTIE, "w", encoding="utf-8") as f:
    try:
        from wagtail.models import Page
        for page in Page.objects.live().public().order_by("path").specific():
            try:
                contenu = page.serializable_data()
            except Exception:  # un type de page exotique ne doit pas arrêter l'extraction
                contenu = {}
            ecrire(f, "wagtail_page", {
                "id": page.pk, "path": page.path, "depth": page.depth, "url_path": page.url_path,
                "title": page.title, "slug": page.slug, "type_de_page": page._meta.label,
                "langue": getattr(getattr(page, "locale", None), "language_code", ""),
                "premiere_publication": page.first_published_at, "derniere_publication": page.last_published_at,
                "description": page.search_description, "contenu": contenu,
            })
    except ImportError:
        pass
    try:
        from wagtail.contrib.redirects.models import Redirect
        with transaction.atomic():
            lignes = list(Redirect.objects.all())
        for r in lignes:
            ecrire(f, "wagtail_redirect", {
                "ancien": r.old_path, "permanente": r.is_permanent,
                "vers_page": r.redirect_page_id, "vers_adresse": r.redirect_link,
            })
    except (ImportError, DatabaseError) as exc:  # application ou table absente : ignoré
        print("Redirections Wagtail ignorées :", type(exc).__name__)
    try:
        from core.models import Audience, DirectoryEntry, Event, Service
    except ImportError:
        Audience = DirectoryEntry = Event = Service = None
    if Event is not None:
        for e in Event.objects.filter(public=True).order_by("start"):
            ecrire(f, "event", champs(e, exclure=("photo",)) | {"tags": list(e.tags.values_list("slug", flat=True))})
        # Seulement les fiches publiques, et pas leurs coordonnées personnelles.
        personnels = {"email", "phone", "address", "postal_code", "latitude", "longitude", "owner", "logo", "photo_promo"}
        for fiche in DirectoryEntry.objects.filter(visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=True):
            ecrire(f, "directory_entry", champs(fiche, exclure=personnels))
        for s in Service.objects.all():
            ecrire(f, "service", champs(s, exclure=("icon",)))
        for a in Audience.objects.all():
            ecrire(f, "audience", champs(a))

print("Écrit dans", SORTIE, "→", compte)
