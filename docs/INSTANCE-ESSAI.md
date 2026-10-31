# Instance d'essai de voisinternet (essai.resdigita.org)

Pour essayer `voisinternet` contre le clone de Keycloak (`key.resdigita.org`) **sans toucher à la production**. Proposée par l'administration : un second gunicorn sur `rosest330`, un autre port, une base PostgreSQL vide, le nom `essai.resdigita.org`. La partie serveur (conteneur, Caddy, DNS, base) est à l'administration ; ce document dit ce que l'application attend.

## Ce que l'application attend
- **Code** : le commit de `main` (le même que la production, pour que l'essai vaille quelque chose).
- **Environnement** : `.env.essai-instance.example` (à copier hors dépôt, droits 600). Valeurs à remplir à part : `DJANGO_SECRET_KEY` et `VOISINTERNET_ANON_PEPPER` (nouveaux, différents de la production), `POSTGRES_PASSWORD`, `OIDC_RP_CLIENT_SECRET` (le même que `key.gv.je`, copié à la main). `DJANGO_ALLOWED_HOSTS` et `DJANGO_CSRF_TRUSTED_ORIGINS` contiennent `essai.resdigita.org`.
- **Dossiers propres** : `DJANGO_STATIC_ROOT`, `DJANGO_MEDIA_ROOT`, `DJANGO_CACHE_DIR` (le cache sert à la limitation de débit et à la déconnexion : ne pas le partager avec la production).
- **Pas de courrier, pas d'annuaire** : `EMAIL_HOST` vide, `VOISINTERNET_REDIRECTIONS=non`. Pas d'inscription de test (la fédération LDAP du clone est en écriture).
- **Accès limité** : mot de passe HTTP ou liste d'adresses dans Caddy, et `robots.txt` (déjà servi par l'application) ; la base est vide, donc aucune donnée personnelle, mais des robots n'ont rien à faire là.

## Mise en route (dans l'ordre, avec l'environnement chargé)
```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate            # dont 0039 à 0042 : vue v_demandes_a_appliquer et demande_marquer
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py loaddata core/fixtures/*.json   # données d'exemple (services, parcours…), facultatif
.venv/bin/gunicorn voisinternet.wsgi:application --bind 127.0.0.1:8092 --workers 2 --timeout 30
```
(`make fixtures-load` charge les fixtures dans l'ordre voulu.) Contrôle : `deploy/smoke.sh https://essai.resdigita.org`.

## Côté clone Keycloak
Pour le client `voisinternet`, sur le clone seulement : adresse de retour de connexion `https://essai.resdigita.org/oidc/callback/` ; adresses de retour de déconnexion et origines `https://essai.resdigita.org/*`.

## À vérifier
Connexion nommée depuis le clone ; lien « compte » vers `key.resdigita.org` ; déconnexion (le clone redemande l'identification) ; `SELECT * FROM v_demandes_a_appliquer;` répond ; `\df demande_marquer` existe ; page « Modération » après avoir ajouté un compte au groupe « Modération » (`/fr/admin/`).
