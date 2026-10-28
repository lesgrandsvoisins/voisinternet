#!/usr/bin/env bash
# Mise à jour du CODE de www.lesgrandsvoisins.com (voisinter-django), avec garde-fous. À lancer DANS le conteneur, depuis le dossier
# du projet, avec l'utilisateur du service :
#     deploy/mise-a-jour.sh BRANCHE_OU_COMMIT --essai     # montre ce qui changerait, ne modifie RIEN
#     deploy/mise-a-jour.sh BRANCHE_OU_COMMIT             # fait la mise à jour du code (pas le redémarrage)
# Réglages (facultatifs) : PROJET, ENV_FILE, DEST (comme deploy/sauvegarde.sh) ;
#   SOURCE=…   dépôt à récupérer (défaut : origin) ; un fichier « git bundle » convient s'il n'y a pas d'accès à GitHub ;
#   OUI=1      ne pas demander de confirmation ;  SANS_SAUVEGARDE=1  passer outre la sauvegarde (à éviter) ;
#   SAUVEGARDE_FAITE="chemin ou texte"   déclare une sauvegarde faite AILLEURS, par exemple celle de l'hôte
#              (scripts/sauvegarde-www.sh de flakeops : SAUVEGARDE_FAITE=/mnt/casiers/backups/www/2026-10-28-0955).
# Garde-fous : refuse s'il n'y a pas de sauvegarde de moins d'une heure (deploy/sauvegarde.sh), refuse si le dossier a des
# modifications locales, ne touche pas à la branche suivie (la mise à jour se fait en « tête détachée »), note le commit d'avant
# pour le retour arrière. Ne redémarre PAS le service : c'est une étape à part, volontaire.
set -uo pipefail
# Charge un fichier d'environnement au format systemd (CLE=valeur, sans interprétation : un « $ » dans une valeur reste littéral).
# Ne PAS faire « . fichier » : le shell prendrait les « $… » pour des variables.
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
REF=${1:-}; ESSAI=0; [ "${2:-}" = "--essai" ] && ESSAI=1
[ -n "$REF" ] || { sed -n 2,13p "$0"; exit 2; }
PROJET=${PROJET:-$(pwd)}; ENV_FILE=${ENV_FILE:-/etc/voisinter-django/voisinter-django.env}; DEST=${DEST:-$HOME/sauvegardes}; SOURCE=${SOURCE:-origin}
PY="$PROJET/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
cd "$PROJET" || { echo "KO dossier du projet introuvable : $PROJET"; exit 2; }
die() { echo "KO   $*"; exit 1; }

# 1. Sauvegarde récente obligatoire.
recente=$(find "$DEST" -maxdepth 1 -type d -name '*-avant-maj' -mmin -60 2>/dev/null | sort | tail -1)
if [ -n "${SAUVEGARDE_FAITE:-}" ]; then echo "OK   sauvegarde déclarée faite : $SAUVEGARDE_FAITE (non contrôlée par ce script : vérifiez qu'elle date d'AVANT cette mise à jour)"
elif [ -z "$recente" ] || [ ! -s "$recente/SHA256SUMS" ]; then
  [ -n "${SANS_SAUVEGARDE:-}" ] && echo "WARN pas de sauvegarde récente : passé outre (SANS_SAUVEGARDE)" || die "aucune sauvegarde de moins d'une heure dans $DEST : lancer deploy/sauvegarde.sh, ou déclarer celle de l'hôte avec SAUVEGARDE_FAITE=…"
else echo "OK   sauvegarde récente : $recente"; fi

# 2. Dossier propre.
[ -z "$(git status --porcelain -uno)" ] || { git status --short -uno; die "modifications locales non validées : les examiner avant (git stash ou git diff)"; }

# 3. Récupération et comparaison.
avant=$(git rev-parse HEAD); echo "Code actuel : $avant ($(git rev-parse --abbrev-ref HEAD))"
git fetch "$SOURCE" "$REF" 2>&1 | tail -3
cible=$(git rev-parse FETCH_HEAD 2>/dev/null) || die "impossible de récupérer « $REF » depuis « $SOURCE » (accès à GitHub ? sinon : SOURCE=/chemin/vers/fichier.bundle)"
echo "Code visé   : $cible"
[ "$avant" != "$cible" ] || { echo "Rien à faire : le code est déjà à ce commit."; exit 0; }
echo "--- Commits qui arrivent ($(git rev-list --count HEAD..FETCH_HEAD)) :"; git log --oneline HEAD..FETCH_HEAD | head -40
git merge-base --is-ancestor HEAD FETCH_HEAD || echo "WARN le code actuel n'est PAS un ancêtre du code visé (historique divergent) : vérifier ce qu'on écrase"
echo "--- Dépendances :"; if git diff --quiet HEAD FETCH_HEAD -- requirements.txt; then echo "inchangées"; else echo "CHANGÉES :"; git diff HEAD FETCH_HEAD -- requirements.txt | grep '^[+-][^+-]'; fi
echo "--- Migrations qui arrivent :"; git diff --name-only --diff-filter=A HEAD FETCH_HEAD -- '*/migrations/*.py' | sed 's/^/  /'
echo "--- Fichiers changés : $(git diff --name-only HEAD FETCH_HEAD | wc -l)"
if [ "$ESSAI" -eq 1 ]; then echo; echo "ESSAI : rien n'a été modifié."; exit 0; fi

# 4. Confirmation, puis mise à jour du code.
if [ -z "${OUI:-}" ]; then read -r -p "Mettre à jour le code vers $cible ? [oui/NON] " r; [ "$r" = oui ] || die "abandon"; fi
[ -n "$recente" ] && echo "$avant" > "$recente/commit-avant.txt"
echo "--- Décomptes AVANT (à comparer après) :"; ( cd "$PROJET" && charger_env "$ENV_FILE" && "$PY" manage.py shell -c "
from core.models import Account, Shortcut, Event, DirectoryEntry
print('  comptes', Account.objects.count(), '| anonymes', Account.objects.filter(user__isnull=True).count(), '| raccourcis', Shortcut.objects.count(), '| évènements', Event.objects.count(), '| fiches', DirectoryEntry.objects.count())" 2>&1 | grep -v 'imported automatically' )
changed_req=1; git diff --quiet HEAD FETCH_HEAD -- requirements.txt && changed_req=0
git checkout --detach FETCH_HEAD 2>&1 | tail -1 || die "git checkout a échoué : le code n'a pas changé"
if [ "$changed_req" -eq 1 ]; then echo "Installation des dépendances…"; "$PROJET/.venv/bin/pip" install -r requirements.txt || die "pip a échoué : revenir en arrière (voir ci-dessous)"; fi
charger_env "$ENV_FILE"
"$PY" manage.py check || die "manage.py check a échoué : revenir en arrière (voir ci-dessous)"
echo "--- Migrations qui seront appliquées au redémarrage :"; "$PY" manage.py migrate --plan | sed 's/^/  /'
cat <<FIN

CODE MIS À JOUR (pas encore redémarré) : $cible
Étapes suivantes, à la main :
  1. redémarrer le service (applique les migrations et collecte les fichiers statiques) :  systemctl restart voisinter-django
     puis surveiller :                                                                      journalctl -u voisinter-django -f
  2. test de fumée :   deploy/smoke.sh https://www.lesgrandsvoisins.com
  3. comparer les décomptes : ./decomptes.sh (doivent égaler ou dépasser ceux affichés plus haut, « Décomptes AVANT »)
RETOUR ARRIÈRE si quelque chose ne va pas :
  git checkout --detach $avant && systemctl restart voisinter-django     (le commit d'avant est aussi dans git-etat.txt de la sauvegarde de l'hôte)
  (les nouvelles tables de la migration 0034 peuvent rester ; pour les retirer : $PY manage.py migrate core 0033 AVANT de revenir au code précédent)
FIN
