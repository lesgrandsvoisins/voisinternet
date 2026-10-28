#!/usr/bin/env bash
# Nombre d'enregistrements du site (lecture seule), pour comparer AVANT et APRÈS une mise à jour.
# À lancer dans le conteneur : PROJET=/var/voisinter/voisinter ./decomptes.sh   (défaut : dossier courant)
set -uo pipefail
PROJET=${PROJET:-$(pwd)}; ENV_FILE=${ENV_FILE:-/etc/voisinter-django/voisinter-django.env}
PY="$PROJET/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
cd "$PROJET" || exit 2; set -a; . "$ENV_FILE"; set +a
"$PY" manage.py shell -c "
from django.contrib.auth import get_user_model
from core.models import Account, Shortcut, Event, DirectoryEntry
print('comptes', Account.objects.count()); print('comptes_anonymes', Account.objects.filter(user__isnull=True).count()); print('utilisateurs', get_user_model().objects.count())
print('raccourcis', Shortcut.objects.count()); print('evenements', Event.objects.count()); print('fiches_annuaire', DirectoryEntry.objects.count())
" 2>&1 | grep -v 'imported automatically'
