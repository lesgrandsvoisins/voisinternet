# Déploiement de www.lesgrandsvoisins.com (voisinter-django)

> **BROUILLON — non vérifié sur le serveur.** Écrit d'après le module Nix `modules/voisinter-django.nix` et `docs/CUTOVER-web.md` du dépôt `chris2fr/flakeops` (branche `rosest330`), sans accès à la machine. À confirmer par la personne qui déploie, puis à retirer de ce brouillon. Aucun secret ici.

## Ce qu'on sait (lu dans la configuration)
- Machine : la T330 (`rosest330`). Le site tourne dans le conteneur NixOS **`voisinter-django`** (service `voisinter-django.service`, gunicorn 4 processus sur `127.0.0.1:8091`), derrière Caddy sur l'hôte. Hôtes servis : `www.`, `new.` et `transition.lesgrandsvoisins.com`.
- Code : `/var/voisinter/voisinter` dans le conteneur (dépôt `lesgrandsvoisins/voisinternet`), environnement Python `/var/voisinter/voisinter/.venv`.
- Réglages : fichier d'environnement `/etc/voisinter-django/voisinter-django.env` (sur l'hôte, monté en lecture seule dans le conteneur). Contenu non lu ici ; modèle : `.env.example`.
- Fichiers servis par Caddy : statiques `/var/www/voisinter-django/static`, médias `/var/www/voisinter-django/media`.
- Au démarrage du service, deux commandes tournent déjà (`ExecStartPre`) : `manage.py migrate --noinput` et `manage.py collectstatic --noinput`. **Les migrations sont donc appliquées automatiquement au redémarrage.**
- Test sans DNS (d'après `docs/CUTOVER-web.md`) : `curl -sI -H 'Host: www.lesgrandsvoisins.com' http://127.0.0.1:8091/`.

## Ce qu'on ne sait pas (à confirmer)
- Quelle branche suit la production (`main` ?) et si `/var/voisinter/voisinter` est bien un dépôt git à jour. **Non vérifié.**
- Le moteur de base de données de production (SQLite ou PostgreSQL ; `CUTOVER-web.md` parle d'une base `voisinter-django` en PostgreSQL). **Non vérifié.**
- L'utilisateur qui lance les commandes dans le conteneur.

## Recette (sauvegarde, mise à jour, vérification, retour arrière)

Trois scripts dans `deploy/`, essayés sur une **simulation locale** (base SQLite, code de `main` puis de la branche de travail) : `sauvegarde.sh`, `mise-a-jour.sh`, `smoke.sh`. **Non essayés sur le vrai serveur.** Ils se lancent dans le conteneur, depuis `/var/voisinter/voisinter`, avec l'utilisateur du service. Le dépôt est public : le serveur récupère le code par `https://github.com/lesgrandsvoisins/voisinternet` sans clé.

Ce qui change entre `main` (production d'après le dernier commit connu, `e8898fe`) et la branche de travail : 15 commits, 45 fichiers, **aucune dépendance Python nouvelle**, **une migration** (`core/migrations/0034`, trois nouvelles tables, aucune table existante modifiée), un réglage ajouté (`LOGIN_REDIRECT_URL_FAILURE`, sans variable d'environnement). Essayé en simulation : la migration s'applique sur l'ancien schéma sans toucher aux données, et `migrate core 0033` la retire (l'ancien code refonctionne ensuite).

**0a. Récupérer les scripts d'abord** : le code en production (`main`) ne les contient pas encore. Dans le conteneur (par exemple `sudo nixos-container root-login voisinter-django`, puis `su -s /bin/bash voisinter-django` ; **non vérifié**) :
```
cd ~ && for f in sauvegarde.sh mise-a-jour.sh smoke.sh; do curl -fsSLO https://raw.githubusercontent.com/lesgrandsvoisins/voisinternet/claude/lesgrandsvoisins-ux-klh29a/deploy/$f; done; chmod +x *.sh
export PROJET=/var/voisinter/voisinter        # puis lancer ./sauvegarde.sh, ./mise-a-jour.sh, ./smoke.sh au lieu de deploy/…
```
Lire les scripts avant de les lancer : ce sont de courts fichiers texte.

**0. Choisir le code à mettre en ligne.** Ne pas fusionner dans `main` pour « essayer » : la mise à jour se fait en tête détachée sur la branche de travail ; `main` n'est pas modifiée. Fusionner dans `main` seulement une fois la mise en ligne jugée bonne.

**1. Sauvegarder** (obligatoire, la mise à jour refuse sans sauvegarde de moins d'une heure) :
```
cd /var/voisinter/voisinter
deploy/sauvegarde.sh        # dossier ~/sauvegardes/AAAAMMJJ-HHMMSS-avant-maj
```
Elle sauvegarde la base (PostgreSQL si `POSTGRES_DB` est défini, sinon SQLite), les médias, le **fichier d'environnement** (droits 600, **secrets** : il contient `VOISINTERNET_ANON_PEPPER`, qui ne doit jamais être perdu ni changé, sinon plus aucun compte anonyme n'est récupérable), le commit déployé, des décomptes (comptes, raccourcis, évènements, fiches) et des sommes SHA-256, puis **vérifie** ce qu'elle a écrit. Elle se termine par « SAUVEGARDE OK » ou « INCOMPLÈTE ».

**2. Copier la sauvegarde hors de la machine** (aujourd'hui aucune copie hors du domicile n'existe) puis vérifier la copie : `scp -r <machine>:~/sauvegardes/<dossier> ~/` puis `cd <dossier> && sha256sum -c SHA256SUMS`. Le dossier contient des secrets : ne le publier nulle part, ne jamais le mettre dans git.

**3. Voir ce qui va changer, sans rien modifier :**
```
deploy/mise-a-jour.sh claude/lesgrandsvoisins-ux-klh29a --essai
```
Elle liste les commits qui arrivent, l'état des dépendances et les migrations.

**4. Mettre à jour le code** (sans redémarrer) :
```
deploy/mise-a-jour.sh claude/lesgrandsvoisins-ux-klh29a
```
Elle refuse s'il manque une sauvegarde récente ou si des fichiers suivis sont modifiés, note le commit d'avant dans le dossier de sauvegarde, passe sur la branche en tête détachée, lance `manage.py check` et affiche la migration prévue.

**5. Redémarrer** (applique la migration et collecte les fichiers statiques) : `systemctl restart voisinter-django`, en surveillant `journalctl -u voisinter-django -f`.

**6. Vérifier :** `deploy/smoke.sh https://www.lesgrandsvoisins.com`, puis regarder à la main l'accueil, « Mon compte » (créer un compte anonyme de test et le fermer), `/fr/account/parcours/`, `/fr/account/inscription/`. Les décomptes de `enregistrements.txt` doivent être identiques ou supérieurs.

**7. Une seule fois, après la première mise en ligne :** charger les parcours guidés d'exemple, `manage.py loaddata core.mission core.missionstep` (le parcours « Ma boîte courriel » y est masqué tant que `B-039` n'est pas résolu). Ne pas le refaire ensuite : cela écraserait les modifications faites dans l'administration.

**Retour arrière du code :** `git checkout --detach <commit-avant.txt> && systemctl restart voisinter-django`. Si on veut aussi retirer les nouvelles tables : `manage.py migrate core 0033` **avant** de revenir au code précédent.

**Restauration complète (si la base est abîmée)** : arrêter le service (`systemctl stop voisinter-django`), puis
- SQLite : copier `base.sqlite3` à l'emplacement de la base (`DJANGO_SQLITE_PATH` ou `var/db.sqlite3`) ;
- PostgreSQL : `pg_restore --clean --if-exists -d <base> base.dump` (ou restaurer dans une base neuve et pointer `POSTGRES_DB` dessus) ;
- médias : `tar -xzf media.tar.gz -C <dossier parent des médias>` ;
- environnement : remettre `environnement.env` en place (droits restreints), **sans modifier** `VOISINTERNET_ANON_PEPPER` ;
puis redémarrer et relancer `smoke.sh`. **La restauration n'a jamais été essayée sur le vrai serveur** : en faire une répétition dans une base de test est la meilleure preuve qu'une sauvegarde vaut quelque chose.

## Tests de non-régression
- **Tests unitaires** : `make test` (149 tests : pages, comptes anonymes et nommés, agenda, annuaire, parcours, Keycloak simulé). À lancer avant toute fusion. **Aucune intégration continue n'existe** pour l'instant : ils ne tournent que si quelqu'un les lance.
- **Test de fumée du site en ligne** : `deploy/smoke.sh [URL]` (lecture seule, aucun compte créé). Vérifié contre une instance locale uniquement, **pas contre la production**. Un échec sur « inscription -> Keycloak » avec `prompt=create` signifie que `KEYCLOAK_REALM_URL` ou `OIDC_RP_CLIENT_ID` manque dans l'environnement du site.
- **Côté serveur** : la suite `scripts/nonreg/` de `flakeops` ne contrôle pas `www.lesgrandsvoisins.com` aujourd'hui ; le test d'inscription dans un navigateur (`inscription-navigateur.py`, non vérifié, jamais lancé) couvre le parcours d'inscription de bout en bout.
- Ce que rien ne teste encore : l'arrivée du courriel de vérification depuis `www`, l'affichage réel des messages du thème Keycloak, l'envoi des courriels de l'agenda (serveur SMTP réel).
