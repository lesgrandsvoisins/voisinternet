# Essai local de voisinternet contre le clone Keycloak (key.resdigita.org)

But : vérifier la connexion, la déconnexion et le compte sous `https://key.resdigita.org/realms/master` **sans toucher à la production** (ni à la base de `voisinternet`, ni à `rosest330`). Tout se passe sur le poste de Chris, avec une base PostgreSQL jetable.

## Avant de commencer
- Les adresses de retour du client `voisinternet` pour `http://localhost:8000` sont déjà ajoutées **sur le clone seulement**.
- **Aucune inscription de test depuis le clone** : la fédération LDAP est en écriture, une inscription créerait un vrai compte dans l'annuaire. Se connecter avec un compte existant, c'est tout.

## Étapes
1. Base jetable : `docker run --rm --name essai-pg -e POSTGRES_PASSWORD=essai -e POSTGRES_DB=essai -p 5433:5432 postgres:17`
2. Dans le dépôt : `cp .env.essai-clone.example .env`, puis remplir **une seule valeur** : `OIDC_RP_CLIENT_SECRET` (le secret du client `voisinternet`, le même que sur `key.gv.je` : à copier depuis `/etc/voisinter-django/voisinter-django.env`, ne le collez nulle part ailleurs). Port ≠ 8000 : changer `DJANGO_PORT` et `DJANGO_CSRF_TRUSTED_ORIGINS`, et demander à l'administration d'ajouter ce port sur le clone.
3. `make setup` (venv, dépendances, migrations dont celles des demandes, données d'exemple), puis `make run`.
4. Ouvrir `http://localhost:8000/fr/account/`.

## À vérifier
- Connexion nommée : le bouton mène à `key.resdigita.org`, on revient connecté·e.
- Même personne retrouvée par `sub` (l'identifiant est identique sous les deux noms ; la base locale est vide, le compte est simplement créé).
- Lien « compte » (Mon compte) : mène à `https://key.resdigita.org/realms/master/account/`.
- Déconnexion : revient à l'accueil local, la session du clone est fermée (rouvrir la page de connexion : le clone redemande l'identification).
- Demandes (PostgreSQL) : `psql` sur la base `essai` : `SELECT * FROM v_demandes_a_appliquer;` répond (vide) et `\df demande_marquer` existe.

## Fin
Arrêter le conteneur (`docker stop essai-pg`, il disparaît seul) et supprimer le `.env` d'essai. Rien n'a été écrit ailleurs.
