#!/usr/bin/env bash
# Lance « manage.py » avec l'environnement du site (fichier d'environnement au format systemd, chargé sans interprétation).
# Usage (dans le conteneur, en tant qu'utilisateur du service) :  deploy/manage.sh check ;  deploy/manage.sh shell ;  deploy/manage.sh loaddata …
set -uo pipefail
charger_env() {
  local f=$1 l k v
  while IFS= read -r l || [ -n "$l" ]; do
    case "$l" in ''|'#'*|';'*) continue;; esac
    k=${l%%=*}; v=${l#*=}; k=${k#export }; k=${k// /}
    [[ "$k" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    case "$v" in \"*\") v=${v#\"}; v=${v%\"};; \'*\') v=${v#\'}; v=${v%\'};; esac
    export "$k=$v"
  done < "$f"
}
PROJET=${PROJET:-${PROJECT:-$(pwd)}}; ENV_FILE=${ENV_FILE:-/etc/voisinter-django/voisinter-django.env}
PY="$PROJET/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
cd "$PROJET" || exit 2
charger_env "$ENV_FILE"
exec "$PY" manage.py "$@"
