#!/usr/bin/env bash
# Redémarre le service www.lesgrandsvoisins.com (voisinter-django) SANS passer par root, attend qu'il réponde, puis lance le test de fumée.
# À lancer DANS le conteneur, avec l'utilisateur du service. Repose sur la règle sudo accordée par l'administration (demande UX n°15) :
# l'utilisateur voisinter-django peut lancer, sans mot de passe, exactement « sudo systemctl restart voisinter-django.service » (rien d'autre).
#     deploy/redemarrer.sh              # redémarre, attend, test de fumée
#     deploy/redemarrer.sh --sans-test  # redémarre et attend seulement
# Réglages (facultatifs) : PORT (défaut 8091), HOTE (défaut www.lesgrandsvoisins.com), ATTENTE (secondes, défaut 90).
set -uo pipefail
PORT=${PORT:-8091}; HOTE=${HOTE:-www.lesgrandsvoisins.com}; ATTENTE=${ATTENTE:-90}
PROJET=${PROJET:-${PROJECT:-$(cd "$(dirname "$0")/.." && pwd)}}
echo "--- Redémarrage du service…"
sudo -n systemctl restart voisinter-django.service || { echo "ÉCHEC : sudo a refusé (la règle de l'administration est-elle en place ?). En root : systemctl restart voisinter-django" >&2; exit 1; }
echo "--- Attente de la réponse (au plus ${ATTENTE} s : migrations et fichiers statiques au démarrage)…"
for ((i = 0; i < ATTENTE; i += 2)); do
  code=$(curl -s -o /dev/null -m 5 -w '%{http_code}' -H "Host: $HOTE" "http://127.0.0.1:$PORT/fr/" 2>/dev/null)
  case "$code" in 200|301|302) echo "    le service répond (HTTP $code) après ~${i} s"; break;; esac
  sleep 2
done
case "${code:-}" in 200|301|302) ;; *) echo "ÉCHEC : le service ne répond pas après ${ATTENTE} s. Voir : journalctl -u voisinter-django -n 60 (en root)" >&2; exit 1;; esac
[ "${1:-}" = "--sans-test" ] && exit 0
echo "--- Test de fumée :"
HOST=$HOTE "$PROJET/deploy/smoke.sh" "http://127.0.0.1:$PORT"
