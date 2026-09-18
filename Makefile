PYTHON := .venv/bin/python
LANGS  := en es ar ko

# Charge .env dans le shell de la recette, sans réinterpréter les caractères
# spéciaux qu'il peut contenir (voir DJANGO_SECRET_KEY).
LOADENV = export $$(grep -v '^\#' .env 2>/dev/null | xargs -d '\n');
# LOADENV2 = eval "$$(grep -v '^\#\|^ *\t*$$' .env 2>/dev/null | sed -e 's/^/export /')"


.DEFAULT_GOAL := help

.PHONY: help venv install setup migrate makemigrations fixtures superuser \
        run test shell messages compilemessages collectstatic clean \
        fixtures-load fixtures-dump cms-load cms-dump blog-import qmd-export qmd-import \
        event-qmd-export event-qmd-import standard-qmd-export standard-qmd-import

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

production:
	git pull
	make install
	make migrate
	make collectstatic

rollout:
	git pull
	make install
	make setup
	make migrate
	make fixtures-load
	make collectstatic

# 	make makemigrations
# 	rsync -a staticfiles/ /var/www/voisinter-django/static

venv: ## Crée l'environnement virtuel .venv
	python3 -m venv .venv

install: ## Installe les dépendances dans .venv
	$(PYTHON) -m pip install -r requirements.txt

setup: venv install migrate fixtures-load ## Première installation : venv, dépendances, migrations, données d'exemple

migrate: ## Applique les migrations
	$(LOADENV) $(PYTHON) manage.py migrate

makemigrations: ## Génère les migrations manquantes
	$(LOADENV) $(PYTHON) manage.py makemigrations

fixtures-load: ## Charge les données d'exemple (services, publics, guide)
	for i in auth.group auth.user core.audience core.guidebook core.servicecategory core.service core.account core.shortcut core.membership core.directorysector core.directoryentry core.directoryentryphoto core.entrysubscription core.event ; do \
		echo $$i; \
		$(LOADENV) $(PYTHON) manage.py loaddata core/fixtures/$$i.json ; \
	done

fixtures-dump: ## Sauvegarde les données d'exemple (services, publics, guide)
	for i in auth.group auth.user core.audience core.guidebook core.servicecategory core.service core.account core.shortcut core.membership core.directorysector core.directoryentry core.directoryentryphoto core.entrysubscription core.event ; do \
		echo $$i; \
		$(LOADENV) $(PYTHON) manage.py dumpdata $$i >core/fixtures/$$i.json ; \
	done

# Un seul fichier plutôt qu'un par modèle (contrairement à fixtures-load/-dump) : Page et
# Revision se référencent mutuellement (latest_revision_id / page_ptr_id), et loaddata ne
# vérifie les clés étrangères qu'une fois tout le fichier passé en base — les charger
# séparément échouerait sur ce cycle.
CMS_FIXTURES := wagtailcore.locale wagtailcore.site wagtailcore.page wagtailcore.revision \
                wagtailimages.image wagtaildocs.document cms.homepage cms.standardpage \
                cms.polepage cms.contactpage cms.associationpage cms.donationpage

cms-load: ## Charge l'arbre de pages Wagtail (cms/fixtures/cms.json) ; les fichiers médias (var/media) se restaurent à part
	$(LOADENV) $(PYTHON) manage.py loaddata cms/fixtures/cms.json

cms-dump: ## Sauvegarde l'arbre de pages Wagtail (cms/fixtures/cms.json) ; pensez à sauvegarder var/media à part
	$(LOADENV) $(PYTHON) manage.py dumpdata $(CMS_FIXTURES) --indent 2 >cms/fixtures/cms.json

blog-import: ## Importe les articles de deploy/ghost-export dans le blog (idempotent)
	$(LOADENV) $(PYTHON) manage.py import_ghost_posts

qmd-export: ## Exporte un article en .qmd : make qmd-export SLUG=mon-article [LANG=fr] [OUT=chemin.qmd]
	$(LOADENV) $(PYTHON) manage.py export_blog_qmd $(SLUG) --lang=$(or $(LANG),fr) $(if $(OUT),--out=$(OUT))

qmd-import: ## Importe/met à jour un article depuis un .qmd : make qmd-import FILE=mon-article.qmd
	$(LOADENV) $(PYTHON) manage.py import_blog_qmd $(FILE)

event-qmd-export: ## Exporte un évènement en .qmd : make event-qmd-export PK=42 [OUT=chemin.qmd]
	$(LOADENV) $(PYTHON) manage.py export_event_qmd $(PK) $(if $(OUT),--out=$(OUT))

event-qmd-import: ## Importe/met à jour un évènement depuis un .qmd : make event-qmd-import FILE=mon-evenement.qmd
	$(LOADENV) $(PYTHON) manage.py import_event_qmd $(FILE)

standard-qmd-export: ## Exporte une page générique en .qmd : make standard-qmd-export SLUG=ma-page [LANG=fr] [OUT=chemin.qmd]
	$(LOADENV) $(PYTHON) manage.py export_standard_qmd $(SLUG) --lang=$(or $(LANG),fr) $(if $(OUT),--out=$(OUT))

standard-qmd-import: ## Importe/met à jour une page générique depuis un .qmd : make standard-qmd-import FILE=ma-page.qmd
	$(LOADENV) $(PYTHON) manage.py import_standard_qmd $(FILE)

superuser: ## Crée un compte administrateur
	$(LOADENV) $(PYTHON) manage.py createsuperuser

run: ## Lance le serveur de développement
	$(LOADENV) $(PYTHON) manage.py runserver $$DJANGO_IP:$$DJANGO_PORT

test: ## Lance les tests
	$(LOADENV) $(PYTHON) manage.py test core cms

shell: ## Ouvre un shell Django
	$(LOADENV) $(PYTHON) manage.py shell

messages: ## Met à jour les fichiers de traduction (.po) pour toutes les langues
	$(LOADENV) $(PYTHON) manage.py makemessages $(foreach l,$(LANGS),-l $(l)) --no-obsolete

compilemessages: ## Compile les traductions (.po -> .mo)
	$(LOADENV) $(PYTHON) manage.py compilemessages $(foreach l,$(LANGS),-l $(l))

collectstatic: ## Rassemble les fichiers statiques pour la production
	$(LOADENV) $(PYTHON) manage.py collectstatic --noinput

clean: ## Supprime les fichiers Python compilés
	find . -name '__pycache__' -not -path './.venv/*' -exec rm -rf {} +
	find . -name '*.pyc' -not -path './.venv/*' -delete
