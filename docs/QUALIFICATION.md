# Environnement de qualification (« staging ») pour www.lesgrandsvoisins.com

> **PROPOSITION — rien n'est mis en place.** La partie serveur (conteneur, Caddy, DNS, Keycloak) relève de l'administration (`flakeops`, branche `ux/…` puis `rosest330`) : ce document dit ce que l'application attend, pas comment le serveur le fournit. Tout ce qui n'est pas vérifié est marqué **non vérifié**.

## Pourquoi
Le 28/10, une première mise en ligne a été faite à la main, derrière une sauvegarde. Elle s'est bien passée, mais chaque changement (code, thème Keycloak, courrier) est aujourd'hui essayé **pour la première fois en production**. Une qualification permet d'essayer d'abord sur une copie : mise à jour, migration, inscription, courriels.

## Principe
Une deuxième instance de l'application, **voisinter-django-qualif**, identique à la production (même code, même recette `deploy/mise-a-jour.sh`), mais :
- **Autre adresse**, par exemple `qualif.lesgrandsvoisins.com`, non référencée : `robots.txt` interdisant tout, accès limité (mot de passe HTTP ou liste d'adresses) pour éviter indexation et robots (la production a reçu 1 956 comptes anonymes, en grande partie de la visite automatique).
- **Autre base de données**, restaurée depuis une sauvegarde de production **rendue anonyme** : courriels, noms, numéros de téléphone, adresses remplacés ; comptes nommés réduits à quelques comptes de test. Jamais de données personnelles réelles dans la qualification.
- **Autre environnement** (`/etc/voisinter-django-qualif/…env`), avec **son propre `VOISINTERNET_ANON_PEPPER`** (celui de la production ne doit pas y être copié) et **un `DJANGO_SECRET_KEY` différent**.
- **Aucun courriel réel** : `EMAIL_HOST` vide (le réglage historique écrit les messages dans la console, voir `settings.py`), sinon la copie des données écrirait à de vrais membres (courriels de l'agenda, de contact).
- **Connexion** : un client OIDC distinct (`voisinternet-qualif`) avec ses propres adresses de retour. Deux options, à choisir par l'administration : (a) le même Keycloak `key.gv.je`, avec des comptes de test ; les inscriptions de test créent de vrais comptes dans le royaume `master`, à nettoyer (le test `inscription-navigateur.py` le fait) ; (b) un royaume ou un Keycloak de qualification, plus propre mais plus lourd. **Non vérifié** : lequel est réalisable à moindre coût.

## Parcours de mise en ligne avec qualification
1. Sauvegarde (script de l'hôte).
2. Mise à jour de la **qualification** : `deploy/mise-a-jour.sh <branche>` (même script, `PROJET` et `ENV_FILE` de la qualification), redémarrage, `deploy/smoke.sh https://qualif…`, `deploy/decomptes.sh`.
3. Tests sur la qualification : inscription réelle dans un navigateur, ajout d'un évènement, parcours guidés, langues (dont l'arabe, de droite à gauche).
4. Seulement ensuite, la **production**, avec la même commande.
Le code mis en ligne est ainsi **exactement** celui qu'on vient d'essayer (même commit).

## Ce que ça demande côté application (peu)
- Rien de nouveau dans le code : tout vient de variables d'environnement (`.env.example`). `DJANGO_ALLOWED_HOSTS` y contient l'adresse de qualification.
- Un réglage `VOISINTERNET_ANON_ACCOUNTS` pouvant différer (essayer `ouvert` ou `ferme` en qualification avant de le changer en production).
- Un script d'anonymisation d'une sauvegarde (`pg_dump` → base de qualification) : **à écrire** ; il doit être revu avec soin car c'est lui qui protège les données personnelles. **Non écrit.**

## Ce que ça demande côté serveur (à évaluer par l'administration)
Un second conteneur calqué sur `modules/voisinter-django.nix` (port différent, dossiers `/var/www/voisinter-django-qualif`, utilisateur et groupe dédiés), un nom Caddy et un nom DNS, une base PostgreSQL séparée, un client Keycloak, et la place disque/mémoire correspondante (la production consomme ~660 Mo de mémoire en pointe d'après le journal du 28/10). **Non estimé.**

## Alternative légère, si la qualification complète est trop lourde
Un conteneur éphémère lancé à la demande depuis la sauvegarde anonymisée, détruit après les tests. Moins pratique pour tester des changements de Keycloak, qui n'a de toute façon qu'une seule instance.
