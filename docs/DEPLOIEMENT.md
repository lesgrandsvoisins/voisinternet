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

## Recette proposée (à valider)
**Avant**
1. Fusionner le travail dans la branche de production (par une demande de fusion relue ; la branche de travail actuelle est `claude/lesgrandsvoisins-ux-klh29a`). Ne pas déployer une branche de travail directement.
2. Lire `CHANGELOG.md` : qu'est-ce qui change, y a-t-il une migration (la dernière : `core/migrations/0034_mission_missionstep_stepcompletion.py`, nouvelles tables seulement, sans toucher aux anciennes).
3. Sauvegarder la base et les médias (`pg_dump -Fc voisinter-django` si PostgreSQL ; copie de `/var/www/voisinter-django/media`).

**Pendant** (dans le conteneur, en tant qu'utilisateur du service)
4. `cd /var/voisinter/voisinter && git fetch && git log --oneline HEAD..origin/<branche>` pour voir ce qui arrive, puis `git pull --ff-only`.
5. Si `requirements.txt` a changé : `.venv/bin/pip install -r requirements.txt`.
6. Redémarrer : `systemctl restart voisinter-django` (applique migrations et fichiers statiques). Surveiller `journalctl -u voisinter-django -f`.
7. **Première mise en ligne des parcours guidés seulement** : `.venv/bin/python manage.py loaddata core.mission core.missionstep` (trois parcours d'exemple). À ne pas refaire ensuite : cela écraserait les modifications faites dans l'administration.

**Après**
8. Lancer le test de fumée : `deploy/smoke.sh https://www.lesgrandsvoisins.com` (voir ci-dessous). Puis regarder à la main : l'accueil, « Mon compte », un parcours, l'écran d'inscription Keycloak (`/fr/account/inscription/`).
9. Vérifier dans l'administration (`/fr/admin/`) que les parcours existent et que `KEYCLOAK_REALM_URL`, `OIDC_RP_CLIENT_ID` sont bien définis dans le fichier d'environnement (aucun nouveau réglage n'est requis par ces changements).

**Retour arrière**
10. `git checkout <commit précédent>` puis `systemctl restart voisinter-django`. Les migrations de cette série ne créent que de nouvelles tables : les laisser en place est sans danger ; pour les retirer, `manage.py migrate core 0033`. Restaurer la base seulement en cas de corruption.

## Tests de non-régression
- **Tests unitaires** : `make test` (149 tests : pages, comptes anonymes et nommés, agenda, annuaire, parcours, Keycloak simulé). À lancer avant toute fusion. **Aucune intégration continue n'existe** pour l'instant : ils ne tournent que si quelqu'un les lance.
- **Test de fumée du site en ligne** : `deploy/smoke.sh [URL]` (lecture seule, aucun compte créé). Vérifié contre une instance locale uniquement, **pas contre la production**.
- **Côté serveur** : la suite `scripts/nonreg/` de `flakeops` ne contrôle pas `www.lesgrandsvoisins.com` aujourd'hui ; le test d'inscription dans un navigateur (`inscription-navigateur.py`, non vérifié, jamais lancé) couvre le parcours d'inscription de bout en bout.
- Ce que rien ne teste encore : l'arrivée du courriel de vérification depuis `www`, l'affichage réel des messages du thème Keycloak, l'envoi des courriels de l'agenda (serveur SMTP réel).
