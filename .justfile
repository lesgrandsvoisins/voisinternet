# Recettes de www.lesgrandsvoisins.com (voisinter-django). « just » sans argument liste les recettes.
# Dans le conteneur, en tant qu'utilisateur du service : PROJECT=/var/voisinter/voisinter (voir ~/.bashrc). En développement :
# le dossier du projet est pris tout seul.
set shell := ["bash", "-uc"]

project := env("PROJECT", justfile_directory())
prod    := "https://www.lesgrandsvoisins.com"
branche := "main"

default:
    @just --list --unsorted

# ----- Développement -----------------------------------------------------------------------------------------------

# Lance les tests (Makefile : charge .env)
test:
    make test

# Serveur de développement
run:
    make run

# ----- Production : à lancer dans le conteneur, avec l'utilisateur du service --------------------------------------

# Où en est le code déployé (commit, branche, fichiers modifiés)
statut:
    @cd {{project}} && echo "commit : $(git rev-parse --short HEAD)  ($(git rev-parse --abbrev-ref HEAD))" && git log --oneline -3 && git status --short -uno

# Nombre d'enregistrements (comptes, anonymes, raccourcis, évènements, fiches) : à comparer avant / après une mise à jour
decomptes:
    PROJET={{project}} {{project}}/deploy/decomptes.sh

# Test de fumée du site en ligne (lecture seule, aucun compte créé)
fumee url=prod:
    {{project}}/deploy/smoke.sh {{url}}

# Sauvegarde faite DEPUIS le conteneur (base, médias, environnement). Préférer celle de l'hôte : scripts/sauvegarde-www.sh de flakeops
sauvegarde:
    PROJET={{project}} {{project}}/deploy/sauvegarde.sh

# Voir ce qu'une mise à jour changerait, sans rien modifier. `dossier` : la sauvegarde de l'hôte faite avant (ex. /mnt/casiers/backups/www/2026-10-28-1052)
essai dossier ref=branche:
    SAUVEGARDE_FAITE={{dossier}} PROJET={{project}} {{project}}/deploy/mise-a-jour.sh {{ref}} --essai

# Mettre à jour le code (demande confirmation ; ne redémarre PAS : voir `redemarrer`, en root)
maj dossier ref=branche:
    SAUVEGARDE_FAITE={{dossier}} PROJET={{project}} {{project}}/deploy/mise-a-jour.sh {{ref}}

# manage.py avec l'environnement du site. Ex. : just manage check ; just manage shell ; just manage loaddata core/fixtures/core.mission.json
manage *args:
    PROJET={{project}} {{project}}/deploy/manage.sh {{args}}

# ----- À lancer en root dans le conteneur ---------------------------------------------------------------------------

# Redémarrer le service (applique les migrations et collecte les statiques). Root uniquement.
redemarrer:
    systemctl restart voisinter-django

# Dernières lignes du journal du service. Root uniquement.
journal n="60":
    journalctl -u voisinter-django -n {{n}} --no-pager
