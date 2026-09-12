PYTHON := .venv/bin/python
LANGS  := en es ar ko

# Charge .env dans le shell de la recette, sans réinterpréter les caractères
# spéciaux qu'il peut contenir (voir DJANGO_SECRET_KEY).
LOADENV = export $$(grep -v '^\#' .env 2>/dev/null | xargs -d '\n');

.DEFAULT_GOAL := help

.PHONY: help venv install setup migrate makemigrations fixtures superuser \
        run test shell messages compilemessages collectstatic clean

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

rollout:
	git pull
	make install
	make setup
	make makemigrations
	make migrate
	make fixtures
	make collectstatic
	rsync -a staticfiles/ /var/www/voisinter-django/static

venv: ## Crée l'environnement virtuel .venv
	python3 -m venv .venv

install: ## Installe les dépendances dans .venv
	$(PYTHON) -m pip install -r requirements.txt

setup: venv install migrate fixtures ## Première installation : venv, dépendances, migrations, données d'exemple

migrate: ## Applique les migrations
	$(LOADENV) $(PYTHON) manage.py migrate

makemigrations: ## Génère les migrations manquantes
	$(LOADENV) $(PYTHON) manage.py makemigrations

fixtures-load: ## Charge les données d'exemple (services, publics, guide)
	for i in core.audience core.guidebook core.service ; do \
		echo $$i; \
		$(LOADENV) $(PYTHON) manage.py loaddata $$i core/fixtures/$$i.json ; \
	done

fixtures-dump: ## Charge les données d'exemple (services, publics, guide)
	for i in core.audience core.guidebook core.service ; do \
		echo $$i; \
		$(LOADENV) $(PYTHON) manage.py dumpdata $$i >core/fixtures/$$i.json ; \
	done

superuser: ## Crée un compte administrateur
	$(LOADENV) $(PYTHON) manage.py createsuperuser

run: ## Lance le serveur de développement
	$(LOADENV) $(PYTHON) manage.py runserver 192.168.123.2:8091

test: ## Lance les tests
	$(LOADENV) $(PYTHON) manage.py test core

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
