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

Trois scripts dans `deploy/`, essayés sur une **simulation locale** (base SQLite, code de `main` puis de la branche de travail) : `sauvegarde.sh`, `mise-a-jour.sh`, `smoke.sh`. **Non essayés sur le vrai serveur.** Ils se lancent dans le conteneur, depuis `/var/voisinter/voisinter`, avec l'utilisateur du service. **Le dépôt `voisinternet` est privé et le serveur n'a pas de clé GitHub** (`CARTE-DES-DEPOTS.md`) : le code et les scripts arrivent par un fichier (`git bundle`) copié à la main, voir 0a. (Une première version de cette page supposait un dépôt public : c'était faux, les `curl` sur `raw.githubusercontent.com` renvoient 404.)

Ce qui change entre `main` (production d'après le dernier commit connu, `e8898fe`) et la branche de travail : 15 commits, 45 fichiers, **aucune dépendance Python nouvelle**, **une migration** (`core/migrations/0034`, trois nouvelles tables, aucune table existante modifiée), un réglage ajouté (`LOGIN_REDIRECT_URL_FAILURE`, sans variable d'environnement). Essayé en simulation : la migration s'applique sur l'ancien schéma sans toucher aux données, et `migrate core 0033` la retire (l'ancien code refonctionne ensuite).

**0a. Les scripts et le code.** Depuis le 28/10, la production suit **`main`**, qui contient les scripts de `deploy/`, `deploy/manage.sh` et le `.justfile`. Dans le conteneur, en tant que `voisinter-django`, le serveur lit directement le dépôt (`origin`) ; `export PROJECT=/var/voisinter/voisinter` (dans `~/.bashrc`, et `~/.bash_profile` doit le lire) puis `$PROJECT/deploy/mise-a-jour.sh main --essai`.

*Si le serveur ne pouvait pas lire GitHub* (dépôt redevenu privé sans clé), repli par fichier : sur une machine qui a accès au dépôt, `git bundle create voisinternet.bundle main ^<commit en production>`, copier le fichier sur la T330 (`scp`), le déposer dans le dossier personnel du conteneur (`/var/lib/nixos-containers/voisinter-django/home/voisinter-django/`, uid 1538, groupe 500) et lancer `SOURCE=$HOME/voisinternet.bundle $PROJECT/deploy/mise-a-jour.sh main --essai`. Noter les `sha256sum` avant et après la copie.

Entrer dans le conteneur : `machinectl shell voisinter-django` puis `su - voisinter-django`, ou `sudo nixos-container root-login voisinter-django` puis `su -s "$(command -v bash)" voisinter-django` (il n'y a pas de `/bin/bash` sur NixOS). `runuser` est réservé à root. Redémarrer le service se fait en root dans le conteneur.

**0. Choisir le code à mettre en ligne.** On met en ligne ce qui est dans `main` (le travail se fait sur `main`, la branche de travail `claude/lesgrandsvoisins-ux-klh29a` n'est plus utilisée depuis le 28/10 ; tout son contenu est dans `main`, elle peut être supprimée sur GitHub). La mise à jour se fait en tête détachée : `git checkout --detach <commit>`. Pour un essai sur autre chose que `main`, une branche temporaire convient, à supprimer ensuite.

**1. Sauvegarder** (obligatoire). **Recommandée : la sauvegarde de l'hôte**, `sudo bash scripts/sauvegarde-www.sh` dans `flakeops` (root, sur la T330) : base PostgreSQL `voisinter-django` (contrôlée), code, médias et statiques, `/etc/voisinter-django` (secrets, dont `VOISINTERNET_ANON_PEPPER`), plus la base Keycloak et l'annuaire LDAP ; elle écrit `/mnt/casiers/backups/www/AAAA-MM-JJ-HHMM` avec des sommes SHA-256. Ensuite, la mise à jour se lance avec `SAUVEGARDE_FAITE=<ce dossier> ./mise-a-jour.sh …` (déclaration : le script ne peut pas la contrôler depuis le conteneur). Sans cette déclaration, la mise à jour refuse s'il n'y a pas de sauvegarde de moins d'une heure faite par `deploy/sauvegarde.sh`, l'alternative **depuis le conteneur** :
```
cd /var/voisinter/voisinter
deploy/sauvegarde.sh        # dossier ~/sauvegardes/AAAAMMJJ-HHMMSS-avant-maj
```
Elle sauvegarde la base (PostgreSQL si `POSTGRES_DB` est défini, sinon SQLite), les médias, le **fichier d'environnement** (droits 600, **secrets** : il contient `VOISINTERNET_ANON_PEPPER`, qui ne doit jamais être perdu ni changé, sinon plus aucun compte anonyme n'est récupérable), le commit déployé, des décomptes (comptes, raccourcis, évènements, fiches) et des sommes SHA-256, puis **vérifie** ce qu'elle a écrit. Elle se termine par « SAUVEGARDE OK » ou « INCOMPLÈTE ».

**2. Copier la sauvegarde hors de la machine** (`/mnt/casiers` est sur la même machine : en cas de panne ou de vol de la T330, la sauvegarde disparaît avec elle ; aucune copie hors du domicile n'existe aujourd'hui) puis vérifier la copie : `scp -r <machine>:~/sauvegardes/<dossier> ~/` puis `cd <dossier> && sha256sum -c SHA256SUMS`. Le dossier contient des secrets : ne le publier nulle part, ne jamais le mettre dans git.

**3. Voir ce qui va changer, sans rien modifier :**
```
deploy/mise-a-jour.sh main --essai
```
Elle liste les commits qui arrivent, l'état des dépendances et les migrations.

**4. Mettre à jour le code** (sans redémarrer) :
```
deploy/mise-a-jour.sh main
```
Elle refuse s'il manque une sauvegarde récente ou si des fichiers suivis sont modifiés, note le commit d'avant dans le dossier de sauvegarde, passe sur la branche en tête détachée, lance `manage.py check` et affiche la migration prévue.

**5. Redémarrer** (applique les migrations et collecte les fichiers statiques), **sans root** : `deploy/redemarrer.sh` (ou `just redemarrer`). Il lance `sudo systemctl restart voisinter-django.service` (seule commande que la règle de l'administration autorise, demande UX n°15), attend que le service réponde, puis lance le test de fumée. En cas de souci, en root : `journalctl -u voisinter-django -f`. Raccourci : `deploy/mise-a-jour.sh <ref> --redemarrer` fait les étapes 4 et 5.

**6. Vérifier :** `deploy/smoke.sh https://www.lesgrandsvoisins.com`, puis regarder à la main l'accueil, « Mon compte » (créer un compte anonyme de test et le fermer), `/fr/account/parcours/`, `/fr/account/inscription/`. Lancer `./decomptes.sh` : les nombres doivent égaler ou dépasser ceux affichés par la mise à jour (« Décomptes AVANT »).

**7. Une seule fois, après la première mise en ligne :** charger les parcours guidés d'exemple, `manage.py loaddata core/fixtures/core.mission.json core/fixtures/core.missionstep.json` (noms de fichiers complets : `core.mission` seul est pris pour un format et échoue) (le parcours « Ma boîte courriel » y est masqué tant que `B-039` n'est pas résolu). Ne pas le refaire ensuite : cela écraserait les modifications faites dans l'administration.

**Retour arrière du code :** `git checkout --detach <commit-avant.txt> && deploy/redemarrer.sh`. Si on veut aussi retirer les nouvelles tables : `manage.py migrate core 0033` **avant** de revenir au code précédent.

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

## Étiquettes (tags) de version
Une étiquette donne un **nom lisible à un commit précis** : « ce qui tournait en production le 28/10 ». Elle sert de cible de retour arrière (`git checkout --detach v0.2.0`) et de repère dans `docs/DEPLOIEMENTS.md`.
- **Schéma : on continue celui du dépôt**, `v0.MINEUR.CORRECTIF` (déjà `v0.1.0` à `v0.1.5`, posées les 12 et 13 septembre). Un **correctif** (`v0.2.1`) à chaque mise en ligne qui change le code du site ; une **mineure** (`v0.3.0`) pour un jalon ou un changement important. Pas pour de la documentation seule. Les dates et les commits sont dans `docs/DEPLOIEMENTS.md`.
- **Rattrapage** (non créé : mon accès à GitHub refuse de pousser des étiquettes, erreur 403) : `v0.1.6` sur `e8898fe` (ce qui tournait avant le 28/10, 50 commits après `v0.1.5`) et `v0.2.0` sur `1f08e1d` (le code qui tourne depuis le 28/10 à 12:38).
- **Comment** (depuis un clone où l'on peut pousser, ou dans GitHub : *Releases → Draft a new release → Choose a tag → Create new tag*, en choisissant le commit) :
  ```
  git fetch origin
  git tag -a v0.1.6 e8898fe -m "Production avant le 28/10"
  git tag -a v0.2.0 1f08e1d -m "Production du 28/10 12:38 : onboarding, parcours guidés, compte anonyme discret, robots.txt, adresses de la boîte"
  git push origin v0.1.6 v0.2.0
  ```
  Une étiquette annotée garde l'auteur et la date. **Ne jamais déplacer une étiquette déjà poussée.**
