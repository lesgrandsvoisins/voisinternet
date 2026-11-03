# Recettes de www.lesgrandsvoisins.com (voisinter-django). « just » sans argument liste les recettes.
# Le Makefile reste la source unique des recettes ; ce fichier en expose les mêmes fonctions sous l'interface
# « just », en déléguant à make. Dans le conteneur, en tant qu'utilisateur du service :
# PROJECT=/var/voisinter/voisinter (voir ~/.bashrc). En développement, le dossier du projet suffit.

set shell := ["bash", "-uc"]

default:
    @just --list --unsorted

# ----- Développement (recettes du Makefile) ----------------------------------------------------------------------

# Crée l'environnement virtuel .venv
venv:
    make venv

# Installe les dépendances dans .venv
install:
    make install

# Première installation : venv, dépendances, migrations, données d'exemple
setup:
    make setup

# Applique les migrations
migrate:
    make migrate

# Génère les migrations manquantes
makemigrations:
    make makemigrations

# Charge les données d'exemple (services, publics, guide)
fixtures-load:
    make fixtures-load

# Sauvegarde les données d'exemple (services, publics, guide)
fixtures-dump:
    make fixtures-dump

# Charge l'arbre de pages Wagtail (cms/fixtures/cms.json) ; les fichiers médias (var/media) se restaurent à part
cms-load:
    make cms-load

# Sauvegarde l'arbre de pages Wagtail (cms/fixtures/cms.json) ; pensez à sauvegarder var/media à part
cms-dump:
    make cms-dump

# Importe les articles de deploy/ghost-export dans le blog (idempotent)
blog-import:
    make blog-import

# Crée un compte administrateur
superuser:
    make superuser

# Lance le serveur de développement
run:
    make run

# Lance les tests (Makefile : charge .env)
test:
    make test

# Ouvre un shell Django
shell:
    make shell

# Met à jour les fichiers de traduction (.po) pour toutes les langues
messages:
    make messages

# Compile les traductions (.po -> .mo)
compilemessages:
    make compilemessages

# Rassemble les fichiers statiques pour la production
collectstatic:
    make collectstatic

# Supprime les fichiers Python compilés
clean:
    make clean

# Exporte un article en .qmd : just qmd-export mon-article [lang=fr] [out=chemin.qmd]
qmd-export slug lang="fr" out="":
    make qmd-export SLUG={{slug}} LANG={{lang}} OUT={{out}}

# Importe/met à jour un article depuis un .qmd : just qmd-import mon-article.qmd
qmd-import file:
    make qmd-import FILE={{file}}

# Exporte un évènement en .qmd : just event-qmd-export 42 [out=chemin.qmd]
event-qmd-export pk out="":
    make event-qmd-export PK={{pk}} OUT={{out}}

# Importe/met à jour un évènement depuis un .qmd : just event-qmd-import mon-evenement.qmd
event-qmd-import file:
    make event-qmd-import FILE={{file}}

# Exporte une page générique en .qmd : just standard-qmd-export ma-page [lang=fr] [out=chemin.qmd]
standard-qmd-export slug lang="fr" out="":
    make standard-qmd-export SLUG={{slug}} LANG={{lang}} OUT={{out}}

# Importe/met à jour une page générique depuis un .qmd : just standard-qmd-import ma-page.qmd
standard-qmd-import file:
    make standard-qmd-import FILE={{file}}

# Exporte un pôle en .qmd : just pole-qmd-export civisme [lang=fr] [out=chemin.qmd]
pole-qmd-export slug lang="fr" out="":
    make pole-qmd-export SLUG={{slug}} LANG={{lang}} OUT={{out}}

# Importe/met à jour un pôle depuis un .qmd : just pole-qmd-import civisme.qmd
pole-qmd-import file:
    make pole-qmd-import FILE={{file}}

# Exporte un projet en .qmd : just project-qmd-export mon-projet [lang=fr] [out=chemin.qmd]
project-qmd-export slug lang="fr" out="":
    make project-qmd-export SLUG={{slug}} LANG={{lang}} OUT={{out}}

# Importe/met à jour un projet depuis un .qmd : just project-qmd-import mon-projet.qmd
project-qmd-import file:
    make project-qmd-import FILE={{file}}

# ----- Production : à lancer dans le conteneur, avec l'utilisateur du service --------------------------------------

# Où en est le code déployé (commit, branche, fichiers modifiés)
statut:
    make statut

# Nombre d'enregistrements (comptes, anonymes, raccourcis, évènements, fiches) : à comparer avant / après une mise à jour
decomptes:
    make decomptes

# Test de fumée du site en ligne (lecture seule, aucun compte créé)
fumee url="https://www.lesgrandsvoisins.com":
    make fumee URL={{url}}

# Sauvegarde faite DEPUIS le conteneur (base, médias, environnement). Préférer celle de l'hôte
sauvegarde:
    make sauvegarde

# Voir ce qu'une mise à jour changerait, sans rien modifier. `dossier` : la sauvegarde de l'hôte faite avant
essai dossier ref="main":
    make essai DOSSIER={{dossier}} REF={{ref}}

# Mettre à jour le code (demande confirmation ; ne redémarre PAS : voir `redemarrer`)
maj dossier ref="main":
    make maj DOSSIER={{dossier}} REF={{ref}}

# manage.py avec l'environnement du site : just manage check ; just manage shell ; just manage loaddata core/fixtures/core.mission.json
manage *args:
    make manage ARGS="{{args}}"

# Redémarrer le service (applique migrations et collecte statiques), attendre qu'il réponde, puis test de fumée.
# Sans root : repose sur la règle sudo de l'administration (demande UX n°15).
redemarrer:
    make redemarrer

# Dernières lignes du journal du service. Root uniquement.
journal n="60":
    make journal N={{n}}

up:
    make up
