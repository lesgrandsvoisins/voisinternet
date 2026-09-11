# Voisinternet

*Ôtez-vous de leur nuage.* Site de voisinter.net, porté par Les Grands Voisins.

Django 6, gabarits serveur et htmx (servi localement). Le site fonctionne sans
JavaScript ; htmx ne fait qu'éviter les rechargements de page.

## Le plan du site est une conjugaison

Toute la navigation vient d'une seule liste, `core/menu.py`. L'en-tête, le
tableau de l'accueil et le pied de page la lisent tous les trois : modifier une
entrée là suffit.

| Personne | Adresse | Rôle |
|---|---|---|
| je Vois | `/je-vois/` | se connecter, mon compte, mes raccourcis |
| tu Vois | `/tu-vois/` | contact, se faire accompagner |
| il ou elle Voit | `/il-ou-elle-voit/` | bénévolat, accompagner l'autre, don de matériel |
| nous Voyons | `/nous-voyons/` | l'association, la transparence |
| vous Voyez | `/vous-voyez/` | l'annuaire : qui fait partie de la communauté |
| ils et elles Voient | `/ils-et-elles-voient/` | dons et partenaires |
| notre Voie | voies.voisinter.net | le guide (BookStack) |
| nos Voix | voix.voisinter.net | le blog (Ghost) |

## L'annuaire : « vous Voyez »

`/vous-voyez/` liste les personnes et structures de la communauté (à la
manière de gdvoisins.com) : un particulier, une association, une entreprise…
Comme pour les donateurs, une fiche n'apparaît publiquement qu'avec le
consentement explicite de la personne ou de la structure concernée (case
« apparaît publiquement »). Chaque fiche a un secteur d'activité (civisme,
arts plastiques…), une description, et selon les cas un courriel, un
téléphone, un site. `/vous-voyez/secteur/<secteur>/` filtre par secteur. Les
secteurs sont des données, gérées dans l'administration.

## Publics : « Vous êtes… »

Sous le bandeau d'accueil, chaque visiteur se reconnaît en mots de tous les
jours (un particulier, une association, une mairie…). Adhérer à l'un de ces
groupes se fait depuis « je Vois » (mon compte), exactement comme pour les
services : ce n'est pas l'annuaire, qui reste public et non personnel.

Le statut juridique (personne physique ou morale, SIRET, RNA) n'a pas sa place
sur l'accueil : il se précisera au moment du compte ou du contrat.

## Comptes

- **Nominatif** : connexion OpenID Connect par le Keycloak des Grands Voisins
  (`core/auth.py`). Les personnes sont identifiées par le `sub` Keycloak, pas
  par leur courriel.
- **Anonyme** : un numéro de 16 chiffres, affiché une seule fois. Seule son
  empreinte HMAC est conservée ; il suffit pour retrouver ses raccourcis sur
  un autre appareil. Les essais de récupération sont limités (10 par quart
  d'heure et par adresse).
- Une personne qui se connecte avec un compte anonyme ouvert peut rattacher
  ses raccourcis à son compte nominatif.

> `VOISINTERNET_ANON_PEPPER` ne doit **jamais** changer une fois des comptes
> créés : ils deviendraient introuvables.

## Développement

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export DJANGO_DEBUG=true
export EnvironmentFile="$(pwd)/.env"
mkdir -p var
python manage.py migrate
python manage.py loaddata initial      # services et livres du guide d'exemple
python manage.py createsuperuser
python manage.py runserver
python manage.py test core
```

L'administration (`/admin/`) permet aux bénévoles de gérer les services, les
livres du guide et les donateurs. Un donateur n'apparaît publiquement que si
la case « apparaît publiquement » est cochée, avec son accord.

## Production

1. Copier `.env.example` en `.env` et le remplir (clés longues et aléatoires).
2. `python manage.py migrate && python manage.py collectstatic`
3. Service systemd : `deploy/voisinternet.service` (gunicorn, 2 processus).
4. Caddy : `deploy/Caddyfile` sert les fichiers statiques, assure HTTPS et HSTS,
   pose une politique de sécurité du contenu stricte, et redirige
   voisinternet.fr, .com et .org vers voisinter.net en gardant le chemin.
   Remplacer `auth.example.org` par l'adresse de votre Keycloak.

SQLite suffit à cette échelle : la sauvegarde est un seul fichier,
`var/db.sqlite3`. Définir `POSTGRES_DB` (et installer `psycopg`) pour passer à
PostgreSQL.

### Keycloak

Créer un client `voisinternet` (confidentiel, flux standard) dans le royaume
des Grands Voisins, avec pour adresse de redirection
`https://voisinter.net/oidc/callback/` et pour adresse après déconnexion
`https://voisinter.net/`. Renseigner `KEYCLOAK_REALM_URL`, `OIDC_RP_CLIENT_ID`
et `OIDC_RP_CLIENT_SECRET`. Sans ces variables, la connexion nominative est
simplement masquée.

### Ghost

Créer une intégration personnalisée dans Ghost et copier sa clé d'API de
contenu dans `GHOST_CONTENT_KEY`. Les trois derniers articles s'affichent sur
l'accueil, mis en cache un quart d'heure ; si le blog est injoignable,
l'accueil s'affiche quand même.

## À compléter

Les passages entre crochets dans les gabarits (`[À compléter]`,
`[document à publier]`) attendent un contenu réel : ateliers, dépôt de
matériel, documents de l'association, modalités de don, et, pour chaque
service, ce que l'association conserve en tant qu'hébergeur.
