# Recettes de www.lesgrandsvoisins.com (voisinter-django). « just » sans argument liste les recettes.
# Ce fichier est autonome : chaque recette fait directement ce que faisait le Makefile (manage.py,
# .env, scripts de deploy/), sans passer par make. Dans le conteneur, en tant qu'utilisateur du
# service : PROJECT=/var/voisinter/voisinter (voir ~/.bashrc). En développement, le dossier du projet
# suffit. Les paramètres sont positionnels (just n'accepte pas « nom=valeur »).

set shell := ["bash", "-uc"]

project  := env("PROJECT", justfile_directory())
prod     := "https://www.lesgrandsvoisins.com"
branche  := "main"
python   := ".venv/bin/python"
loadenv  := "export $(grep -v '^\\#' .env 2>/dev/null | xargs -d '\\n'); "

default:
    @just --list --unsorted

# ----- Développement -----------------------------------------------------------------------------------------------

# Crée l'environnement virtuel .venv
venv:
    python3 -m venv .venv

# Installe les dépendances dans .venv
install:
    {{python}} -m pip install -r requirements.txt

# Première installation : venv, dépendances, migrations, données d'exemple
setup: venv install migrate fixtures-load

# Applique les migrations
migrate:
    {{loadenv}} {{python}} manage.py migrate

# Génère les migrations manquantes
makemigrations:
    {{loadenv}} {{python}} manage.py makemigrations

# Charge les données d'exemple (services, publics, guide)
fixtures-load:
    for i in auth.group auth.user core.audience core.guidebook core.servicecategory core.service core.account core.shortcut core.membership core.directorysector core.directoryentry core.directoryentryphoto core.entrysubscription core.event core.mission core.missionstep; do echo "$i"; {{loadenv}} {{python}} manage.py loaddata "core/fixtures/$i.json"; done

# Sauvegarde les données d'exemple (services, publics, guide)
fixtures-dump:
    for i in auth.group auth.user core.audience core.guidebook core.servicecategory core.service core.account core.shortcut core.membership core.directorysector core.directoryentry core.directoryentryphoto core.entrysubscription core.event core.mission core.missionstep; do echo "$i"; {{loadenv}} {{python}} manage.py dumpdata "$i" > "core/fixtures/$i.json"; done

# Charge l'arbre de pages Wagtail (cms/fixtures/cms.json) ; les fichiers médias (var/media) se restaurent à part
cms-load:
    {{loadenv}} {{python}} manage.py loaddata cms/fixtures/cms.json

# Sauvegarde l'arbre de pages Wagtail (cms/fixtures/cms.json) ; pensez à sauvegarder var/media à part
cms-dump:
    {{loadenv}} {{python}} manage.py dumpdata wagtailcore.locale wagtailcore.site wagtailcore.page wagtailcore.revision wagtailimages.image wagtaildocs.document cms.homepage cms.standardpage cms.polepage cms.contactpage cms.associationpage cms.donationpage --indent 2 > cms/fixtures/cms.json

# Importe les articles de deploy/ghost-export dans le blog (idempotent)
blog-import:
    {{loadenv}} {{python}} manage.py import_ghost_posts

# Exporte un article en .qmd : just qmd-export mon-article [lang] [out]
qmd-export slug lang="fr" out="":
    {{loadenv}} {{python}} manage.py export_blog_qmd {{slug}} --lang={{lang}} {{ if out != "" { "--out=" + out } else { "" } }}

# Importe/met à jour un article depuis un .qmd : just qmd-import mon-article.qmd
qmd-import file:
    {{loadenv}} {{python}} manage.py import_blog_qmd {{file}}

# Exporte un évènement en .qmd : just event-qmd-export 42 [out]
event-qmd-export pk out="":
    {{loadenv}} {{python}} manage.py export_event_qmd {{pk}} {{ if out != "" { "--out=" + out } else { "" } }}

# Importe/met à jour un évènement depuis un .qmd : just event-qmd-import mon-evenement.qmd
event-qmd-import file:
    {{loadenv}} {{python}} manage.py import_event_qmd {{file}}

# Exporte une page générique en .qmd : just standard-qmd-export ma-page [lang] [out]
standard-qmd-export slug lang="fr" out="":
    {{loadenv}} {{python}} manage.py export_standard_qmd {{slug}} --lang={{lang}} {{ if out != "" { "--out=" + out } else { "" } }}

# Importe/met à jour une page générique depuis un .qmd : just standard-qmd-import ma-page.qmd
standard-qmd-import file:
    {{loadenv}} {{python}} manage.py import_standard_qmd {{file}}

# Exporte un pôle en .qmd : just pole-qmd-export civisme [lang] [out]
pole-qmd-export slug lang="fr" out="":
    {{loadenv}} {{python}} manage.py export_pole_qmd {{slug}} --lang={{lang}} {{ if out != "" { "--out=" + out } else { "" } }}

# Importe/met à jour un pôle depuis un .qmd : just pole-qmd-import civisme.qmd
pole-qmd-import file:
    {{loadenv}} {{python}} manage.py import_pole_qmd {{file}}

# Exporte un projet en .qmd : just project-qmd-export mon-projet [lang] [out]
project-qmd-export slug lang="fr" out="":
    {{loadenv}} {{python}} manage.py export_project_qmd {{slug}} --lang={{lang}} {{ if out != "" { "--out=" + out } else { "" } }}

# Importe/met à jour un projet depuis un .qmd : just project-qmd-import mon-projet.qmd
project-qmd-import file:
    {{loadenv}} {{python}} manage.py import_project_qmd {{file}}

# Crée un compte administrateur
superuser:
    {{loadenv}} {{python}} manage.py createsuperuser

# Lance le serveur de développement
run:
    {{loadenv}} {{python}} manage.py runserver $DJANGO_IP:$DJANGO_PORT

# Lance les tests (charge .env)
test:
    {{loadenv}} {{python}} manage.py test core cms

# Ouvre un shell Django
shell:
    {{loadenv}} {{python}} manage.py shell

# Met à jour les fichiers de traduction (.po) pour toutes les langues
messages:
    {{loadenv}} {{python}} manage.py makemessages -l en -l es -l ar -l ko --no-obsolete

# Compile les traductions (.po -> .mo)
compilemessages:
    {{loadenv}} {{python}} manage.py compilemessages -l en -l es -l ar -l ko

# Rassemble les fichiers statiques pour la production
collectstatic:
    {{loadenv}} {{python}} manage.py collectstatic --noinput

# Supprime les fichiers Python compilés
clean:
    find . -name '__pycache__' -not -path './.venv/*' -exec rm -rf {} +
    find . -name '*.pyc' -not -path './.venv/*' -delete

# ----- Production : à lancer dans le conteneur, avec l'utilisateur du service --------------------------------------

# Où en est le code déployé (commit, branche, fichiers modifiés)
statut:
    @cd {{project}} && echo "commit : $(git rev-parse --short HEAD)  ($(git rev-parse --abbrev-ref HEAD))" && git log --oneline -3 && git status --short -uno

# Nombre d'enregistrements (comptes, anonymes, raccourcis, évènements, fiches) : à comparer avant / après une mise à jour
decomptes:
    PROJET={{project}} {{project}}/deploy/decomptes.sh

# Test de fumée du site en ligne (lecture seule, aucun compte créé) : just fumee [url]
fumee url=prod:
    {{project}}/deploy/smoke.sh {{url}}

# Sauvegarde faite DEPUIS le conteneur (base, médias, environnement). Préférer celle de l'hôte
sauvegarde:
    PROJET={{project}} {{project}}/deploy/sauvegarde.sh

# Voir ce qu'une mise à jour changerait, sans rien modifier. `dossier` : la sauvegarde de l'hôte faite avant (ex. /mnt/casiers/backups/www/2026-10-28-1052)
essai dossier ref=branche:
    SAUVEGARDE_FAITE={{dossier}} PROJET={{project}} {{project}}/deploy/mise-a-jour.sh {{ref}} --essai

# Mettre à jour le code (demande confirmation ; ne redémarre PAS : voir `redemarrer`)
maj dossier ref=branche:
    SAUVEGARDE_FAITE={{dossier}} PROJET={{project}} {{project}}/deploy/mise-a-jour.sh {{ref}}

# manage.py avec l'environnement du site : just manage check ; just manage shell ; just manage loaddata core/fixtures/core.mission.json
manage *args:
    PROJET={{project}} {{project}}/deploy/manage.sh {{args}}

# Redémarrer le service (applique migrations et collecte statiques), attendre qu'il réponde, puis test de fumée.
# Sans root : repose sur la règle sudo de l'administration (demande UX n°15).
redemarrer:
    PROJET={{project}} {{project}}/deploy/redemarrer.sh

# Dernières lignes du journal du service. Root uniquement. : just journal [n]
journal n="60":
    journalctl -u voisinter-django -n {{n}} --no-pager

# Updates and restarts server without database update
cosmetic-up:
    git pull
    ./deploy/redemarrer.sh

# Mise à jour complète : pull + install + migrate + collectstatic
production:
    git pull
    just install
    just migrate
    just collectstatic

# Mise à jour complète : pull + install + setup + migrate + fixtures + collectstatic
rollout:
    git pull
    just install
    just setup
    just migrate
    just fixtures-load
    just collectstatic
