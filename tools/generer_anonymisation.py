"""
Génère deploy/anonymisation.sql : l'anonymisation d'une COPIE de la base de production (jamais de la production elle-même).
Lit les vrais modèles (colonnes traduites _fr/_en/_es/_ar/_ko comprises) pour ne rien oublier si un champ est ajouté.

    .venv/bin/python manage.py shell < tools/generer_anonymisation.py      (écrit deploy/anonymisation.sql)

Principe : rien de personnel ne doit survivre ; la structure, les identifiants numériques et les contenus éditoriaux publics restent.
"""
from django.apps import apps
from django.db import models as dj_models

LANGS = ("fr", "en", "es", "ar", "ko")
out = []


def table(app, model):
    return apps.get_model(app, model)._meta.db_table


def colonnes(app, model, nom):
    """Le champ et ses variantes de langue qui existent réellement."""
    m = apps.get_model(app, model)
    existants = {f.column for f in m._meta.concrete_fields}
    return [c for c in [nom] + [f"{nom}_{l}" for l in LANGS] if c in existants]


def vide(app, model, noms, ou=""):
    """Met à '' (ou NULL si la colonne l'accepte) les champs donnés, langues comprises."""
    m = apps.get_model(app, model)
    sets = []
    for nom in noms:
        for c in colonnes(app, model, nom):
            champ = next(f for f in m._meta.concrete_fields if f.column == c)
            sets.append(f"{c} = NULL" if champ.null else f"{c} = ''")
    if sets:
        out.append(f"UPDATE {table(app, model)} SET {', '.join(sets)}{(' WHERE ' + ou) if ou else ''};")


def sup(app, model, ou=""):
    out.append(f"DELETE FROM {table(app, model)}{(' WHERE ' + ou) if ou else ''};")


en_tete = """-- Anonymisation d'une COPIE de la base de www.lesgrandsvoisins.com (voisinter-django). GÉNÉRÉ par tools/generer_anonymisation.py : ne pas éditer à la main.
-- NE JAMAIS l'exécuter sur la base de production. À lancer UNIQUEMENT sur une base de qualification restaurée depuis une sauvegarde,
-- dans une transaction, puis vérifier avec les requêtes de contrôle en fin de fichier (elles doivent toutes renvoyer 0).
-- Pas de secrets ici. Écrit pour PostgreSQL ; syntaxe volontairement simple (UPDATE/DELETE, || et CAST) pour rester portable.
-- Reste à faire HORS de ce fichier : ne pas copier le dossier media/ (photos de personnes) ; EMAIL_HOST vide ; SECRET_KEY et
-- VOISINTERNET_ANON_PEPPER distincts ; remplacer QUALIF_NOM_DE_DOMAINE ci-dessous par le nom de la qualification.
BEGIN;
"""
out.append(en_tete)

out.append("-- 1. Données de session et journaux : vidés (les sessions contiennent des numéros de compte anonyme en clair).")
for app, model in [("sessions", "Session"), ("admin", "LogEntry")]:
    sup(app, model)
for app, model in [("wagtailcore", "ModelLogEntry"), ("wagtailcore", "PageLogEntry"), ("wagtailcore", "CommentReply"), ("wagtailcore", "Comment")]:
    sup(app, model)
try:
    apps.get_model("wagtailforms", "FormSubmission"); sup("wagtailforms", "FormSubmission")
except LookupError:
    pass

out.append("\n-- 2. Messages reçus par le site (formulaires de contact) : vidés.")
sup("core", "EntryMessage"); sup("cms", "AuthorMessage")

out.append("\n-- 3. Utilisateurs : identité remplacée, mot de passe local inutilisable (la connexion se fait par Keycloak de qualification).")
t = table("auth", "User")
out.append(f"UPDATE {t} SET username = 'test-' || CAST(id AS TEXT), first_name = 'Test', last_name = 'Utilisateur ' || CAST(id AS TEXT), "
           f"email = 'test-' || CAST(id AS TEXT) || '@exemple.invalid', password = '!anonymise', last_login = NULL;")

out.append("\n-- 4. Comptes : l'empreinte du numéro anonyme est supprimée (elle dépend du secret de production).")
out.append(f"UPDATE {table('core','Account')} SET number_digest = NULL;")

out.append("\n-- 5. Annuaire : coordonnées retirées pour TOUTES les fiches ; fiches non publiques ou non validées : texte libre vidé aussi.")
vide("core", "DirectoryEntry", ["email", "phone", "address", "postal_code", "website", "video_url", "cta_link"])
from core.models import DirectoryEntry
nonpub = f"NOT (visibility = '{DirectoryEntry.VISIBILITY_PUBLIC}' AND approved)"
vide("core", "DirectoryEntry", ["name", "title", "tagline", "description", "cta_intro", "cta_label", "city", "region", "logo", "photo_promo"], ou=nonpub)
out.append("-- Le slug d'une fiche est tiré du nom de la personne : remplacé lui aussi.")
out.append(f"UPDATE {table('core','DirectoryEntry')} SET name = 'Fiche test ' || CAST(id AS TEXT), name_fr = 'Fiche test ' || CAST(id AS TEXT), "
           f"slug = 'fiche-test-' || CAST(id AS TEXT) WHERE {nonpub};")
sup("core", "DirectoryEntryPhoto", ou=f"entry_id IN (SELECT id FROM {table('core','DirectoryEntry')} WHERE {nonpub})")
vide("core", "DirectoryEntryPhoto", ["caption"])

out.append("\n-- 6. Dons : notes libres vidées ; noms de donateurs remplacés.")
vide("core", "Contribution", ["note"])
vide("core", "Donor", ["name"])
d = table("core", "Donor")
out.append(f"UPDATE {d} SET name = 'Donateur ' || CAST(id AS TEXT), name_fr = 'Donateur ' || CAST(id AS TEXT);")

out.append("\n-- 7. Agenda : lien de visioconférence retiré partout ; textes des évènements non publiés vidés.")
vide("core", "Event", ["online_url"])
vide("core", "Event", ["description", "location"], ou="NOT public")
e = table("core", "Event")
out.append(f"UPDATE {e} SET title = 'Évènement test ' || CAST(id AS TEXT), title_fr = 'Évènement test ' || CAST(id AS TEXT), "
           f"slug = 'evenement-test-' || CAST(id AS TEXT) WHERE NOT public;")

out.append("\n-- 8. Auteurs du blog : courriel retiré.")
vide("cms", "Author", ["email"])

out.append("\n-- 9. Adresses du site : à remplacer par le nom de la qualification (sinon les liens absolus pointent vers la production).")
out.append("UPDATE wagtailcore_site SET hostname = 'QUALIF_NOM_DE_DOMAINE', port = 443, is_default_site = TRUE;")
if apps.is_installed("django.contrib.sites"):
    out.append("UPDATE django_site SET domain = 'QUALIF_NOM_DE_DOMAINE', name = 'qualification';")

out.append("\n-- Contrôles : chaque requête doit renvoyer 0 après anonymisation.")
ctl = [
    (f"SELECT COUNT(*) FROM {table('auth','User')} WHERE email NOT LIKE '%@exemple.invalid' OR password <> '!anonymise'"),
    (f"SELECT COUNT(*) FROM {table('core','Account')} WHERE number_digest IS NOT NULL"),
    (f"SELECT COUNT(*) FROM {table('core','DirectoryEntry')} WHERE email <> '' OR phone <> '' OR address <> ''"),
    "SELECT COUNT(*) FROM django_session",
    f"SELECT COUNT(*) FROM {table('core','EntryMessage')}",
    f"SELECT COUNT(*) FROM {table('cms','AuthorMessage')}",
    f"SELECT COUNT(*) FROM {table('core','Event')} WHERE online_url <> ''",
    f"SELECT COUNT(*) FROM {table('core','Donor')} WHERE name NOT LIKE 'Donateur %'",
    f"SELECT COUNT(*) FROM {table('core','DirectoryEntry')} WHERE NOT (visibility = '{DirectoryEntry.VISIBILITY_PUBLIC}' AND approved) AND (slug NOT LIKE 'fiche-test-%' OR name NOT LIKE 'Fiche test %')",
    f"SELECT COUNT(*) FROM {table('core','Event')} WHERE NOT public AND slug NOT LIKE 'evenement-test-%'",
    "SELECT COUNT(*) FROM wagtailcore_site WHERE hostname <> 'QUALIF_NOM_DE_DOMAINE'",
]
for c in ctl:
    out.append(c + ";")
out.append("\nCOMMIT;")
open("deploy/anonymisation.sql", "w", encoding="utf-8").write("\n".join(out) + "\n")
print("deploy/anonymisation.sql écrit :", sum(1 for l in out if l.startswith(("UPDATE", "DELETE"))), "instructions")
