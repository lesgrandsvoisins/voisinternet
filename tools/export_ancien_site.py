"""
Extrait le contenu PUBLIC de l'ancien site (old.lesgrandsvoisins.com, dépôt `lesgrandsvoisins/sites-faciles`,
branche `lesgrandsvoisins`) pour préparer sa reprise dans www.lesgrandsvoisins.com : pages à reprendre,
billets de blog, redirections à écrire. Lecture seule, rien n'est modifié.

Usage (depuis le dossier du dépôt sites-faciles, avec son environnement Python et ses variables d'environnement) :

    SORTIE=/tmp/ancien-site .venv/bin/python manage.py shell < /chemin/vers/voisinternet/tools/export_ancien_site.py

Produit, dans le dossier SORTIE (créé au besoin) :
  - contenu.jsonl        : une ligne JSON par élément, champ « type » :
                           « page » (pages Wagtail publiées, billets de blog et fiches d'annuaire compris, avec le contenu
                           des champs et des StreamField), « site » (noms de domaine), « categorie », « etiquette »,
                           « auteur », « menu » (wagtailmenus : menu principal, menus plats), « redirection » (Wagtail),
                           « document » et « image » (titre, nom de fichier, taille, adresse — pas les fichiers) ;
  - adresses.csv         : une ligne par page publiée (adresse publique, titre, type, langue, dates, parent) —
                           la base de la table `LEGACY_REDIRECTS` de `core/urls.py` (colonne « nouvelle_adresse »
                           à remplir à la main) ;
  - resume.txt           : décompte par type.
Jamais extraits : comptes, utilisateurs, mots de passe, formulaires reçus, brouillons, journaux.
Chaque rubrique est isolée : un type introuvable ou une erreur n'arrête pas les autres (elle est notée dans resume.txt).
"""
import csv
import json
import os
import traceback
from datetime import date, datetime

SORTIE = os.environ.get("SORTIE", "ancien-site")
os.makedirs(SORTIE, exist_ok=True)
compte = {}
erreurs = []


def simple(valeur):
    if isinstance(valeur, (datetime, date)):
        return valeur.isoformat()
    return valeur


def champs(obj, exclure=()):
    """Champs simples d'un objet (valeurs sérialisables), sans les relations."""
    out = {}
    for champ in obj._meta.concrete_fields:
        if champ.name in exclure or champ.is_relation:
            continue
        out[champ.name] = simple(getattr(obj, champ.attname))
    return out


def ecrire(f, type_, data):
    f.write(json.dumps({"type": type_, **data}, ensure_ascii=False, default=str) + "\n")
    compte[type_] = compte.get(type_, 0) + 1


def rubrique(nom):
    """Décorateur : exécute la rubrique et note l'erreur sans interrompre les suivantes."""
    def decorateur(fonction):
        try:
            fonction()
        except ImportError:
            erreurs.append(f"{nom} : application absente (ignoré)")
        except Exception:
            erreurs.append(f"{nom} : {traceback.format_exc(limit=3)}")
        return fonction
    return decorateur


def adresse_publique(page):
    try:
        return page.get_full_url() or page.url or ""
    except Exception:
        return page.url_path


with open(os.path.join(SORTIE, "contenu.jsonl"), "w", encoding="utf-8") as f, \
        open(os.path.join(SORTIE, "adresses.csv"), "w", encoding="utf-8", newline="") as g:
    csvw = csv.writer(g)
    csvw.writerow(["adresse_publique", "chemin", "titre", "type_de_page", "langue",
                   "premiere_publication", "derniere_publication", "parent", "nouvelle_adresse"])

    @rubrique("pages")
    def _pages():
        from wagtail.models import Page
        parents = {}
        for page in Page.objects.live().public().order_by("path").specific():
            parents[page.path] = page.title
            try:
                contenu = page.serializable_data()
            except Exception:  # un type de page exotique ne doit pas arrêter l'extraction
                contenu = {}
            extra = {}
            for relation in ("tags", "blog_categories", "authors"):
                try:
                    extra[relation] = [str(x) for x in getattr(page, relation).all()]
                except Exception:
                    pass
            if hasattr(page, "date"):
                extra["date"] = simple(page.date)
            langue = getattr(getattr(page, "locale", None), "language_code", "")
            ecrire(f, "page", {
                "id": page.pk, "path": page.path, "depth": page.depth, "url_path": page.url_path,
                "adresse": adresse_publique(page), "title": page.title, "slug": page.slug,
                "type_de_page": page._meta.label, "langue": langue,
                "premiere_publication": simple(page.first_published_at),
                "derniere_publication": simple(page.last_published_at),
                "description": page.search_description, **extra, "contenu": contenu,
            })
            csvw.writerow([adresse_publique(page), page.url_path, page.title, page._meta.label, langue,
                           simple(page.first_published_at), simple(page.last_published_at),
                           parents.get(page.path[:-4], ""), ""])

    @rubrique("sites")
    def _sites():
        from wagtail.models import Site
        for site in Site.objects.all():
            ecrire(f, "site", {"hostname": site.hostname, "port": site.port, "defaut": site.is_default_site,
                               "racine": site.root_page.url_path})

    @rubrique("categories")
    def _categories():
        from wagtail_village_blog.models import Category
        for categorie in Category.objects.all():
            ecrire(f, "categorie", champs(categorie))

    @rubrique("etiquettes")
    def _etiquettes():
        from taggit.models import Tag
        for etiquette in Tag.objects.all():
            ecrire(f, "etiquette", champs(etiquette))

    @rubrique("auteurs")
    def _auteurs():
        from wagtail_village_blog.models import Person
        for personne in Person.objects.all():
            # Nom et présentation publics seulement : aucun champ de contact.
            ecrire(f, "auteur", {k: v for k, v in champs(personne).items()
                                 if not any(m in k.lower() for m in ("mail", "phone", "tel", "address", "contact"))})

    @rubrique("menus")
    def _menus():
        from wagtailmenus.models import FlatMenu, MainMenu
        for menu in MainMenu.objects.all():
            ecrire(f, "menu", {"genre": "principal", "site": str(menu.site),
                               "elements": [{"texte": i.link_text, "adresse": i.relative_url(menu.site) if hasattr(i, "relative_url") else "",
                                             "page": getattr(i.link_page, "url_path", "")}
                                            for i in menu.get_menu_items_manager().all()]})
        for menu in FlatMenu.objects.all():
            ecrire(f, "menu", {"genre": "plat", "handle": menu.handle, "titre": menu.title, "site": str(menu.site),
                               "elements": [{"texte": i.link_text,
                                             "page": getattr(i.link_page, "url_path", ""),
                                             "url": i.link_url}
                                            for i in menu.get_menu_items_manager().all()]})

    @rubrique("redirections")
    def _redirections():
        from wagtail.contrib.redirects.models import Redirect
        for r in Redirect.objects.all():
            ecrire(f, "redirection", {
                "ancienne": r.old_path, "site": str(r.site) if r.site_id else "",
                "vers_page": getattr(r.redirect_page, "url_path", "") if r.redirect_page_id else "",
                "vers_lien": r.redirect_link, "permanente": r.is_permanent,
            })

    @rubrique("documents")
    def _documents():
        from wagtail.documents import get_document_model
        for doc in get_document_model().objects.all():
            try:
                taille = doc.file.size
            except Exception:
                taille = None
            ecrire(f, "document", {"id": doc.pk, "titre": doc.title, "fichier": doc.filename, "taille": taille,
                                   "adresse": doc.url, "cree": simple(doc.created_at)})

    @rubrique("images")
    def _images():
        from wagtail.images import get_image_model
        for image in get_image_model().objects.all():
            ecrire(f, "image", {"id": image.pk, "titre": image.title, "fichier": image.filename,
                                "largeur": image.width, "hauteur": image.height, "cree": simple(image.created_at)})

with open(os.path.join(SORTIE, "resume.txt"), "w", encoding="utf-8") as r:
    r.write("Décompte par type :\n")
    for type_, n in sorted(compte.items()):
        r.write(f"  {type_}: {n}\n")
    if erreurs:
        r.write("\nRubriques en erreur ou ignorées :\n")
        for e in erreurs:
            r.write(f"  - {e}\n")
print(open(os.path.join(SORTIE, "resume.txt"), encoding="utf-8").read())
