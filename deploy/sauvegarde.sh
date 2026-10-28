#!/usr/bin/env bash
# Sauvegarde AVANT mise à jour de www.lesgrandsvoisins.com (voisinter-django). Lecture seule sur le site : rien n'est modifié.
# À lancer DANS le conteneur, depuis le dossier du projet, avec l'utilisateur du service ou root :
#     deploy/sauvegarde.sh
# Réglages (variables d'environnement, toutes facultatives) :
#   PROJET    dossier du projet               (défaut : dossier courant)
#   ENV_FILE  fichier d'environnement du site (défaut : /etc/voisinter-django/voisinter-django.env)
#   DEST      dossier des sauvegardes         (défaut : $HOME/sauvegardes)
#   SANS_ENV=1  ne pas copier le fichier d'environnement (déconseillé : il contient VOISINTERNET_ANON_PEPPER)
# Contenu : base de données (PostgreSQL si POSTGRES_DB est défini, sinon SQLite), médias, copie du fichier d'environnement
# (droits 600 : SECRETS, ne jamais le publier ni le mettre dans git), commit déployé, nombre d'enregistrements, sommes SHA-256.
# La sauvegarde est VÉRIFIÉE avant de conclure : un échec de vérification donne un code de retour non nul.
set -uo pipefail
PROJET=${PROJET:-$(pwd)}; ENV_FILE=${ENV_FILE:-/etc/voisinter-django/voisinter-django.env}; DEST=${DEST:-$HOME/sauvegardes}
PY="$PROJET/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
cd "$PROJET" || { echo "KO   dossier du projet introuvable : $PROJET"; exit 2; }
ko=0; ok() { echo "OK   $*"; }; ko() { echo "KO   $*"; ko=1; }
[ -r "$ENV_FILE" ] || { echo "KO   fichier d'environnement illisible : $ENV_FILE (le définir avec ENV_FILE=…)"; exit 2; }

horodatage=$(date +%Y%m%d-%H%M%S); OUT="$DEST/$horodatage-avant-maj"
umask 077; mkdir -p "$OUT" || { echo "KO   impossible de créer $OUT"; exit 2; }
echo "Sauvegarde dans $OUT"

# Charge les réglages du site sans rien afficher (les valeurs restent dans ce processus).
set -a; . "$ENV_FILE"; set +a

# 1. Code déployé : de quoi revenir en arrière.
{ echo "date: $(date -Is)"; echo "commit: $(git rev-parse HEAD 2>/dev/null)"; echo "branche: $(git rev-parse --abbrev-ref HEAD 2>/dev/null)"; echo "--- modifications locales non validées :"; git status --short -uno 2>/dev/null; } > "$OUT/etat-code.txt"
ok "commit déployé noté : $(sed -n 2p "$OUT/etat-code.txt")"
git status --short -uno 2>/dev/null | grep -q . && echo "WARN modifications locales non validées dans le dossier du projet (voir etat-code.txt) : elles seraient bloquantes pour un git pull"

# 2. Base de données.
if [ -n "${POSTGRES_DB:-}" ]; then
  export PGPASSWORD="${POSTGRES_PASSWORD:-}"
  args=(-Fc -d "$POSTGRES_DB"); [ -n "${POSTGRES_HOST:-}" ] && args+=(-h "$POSTGRES_HOST"); [ -n "${POSTGRES_PORT:-}" ] && args+=(-p "$POSTGRES_PORT"); [ -n "${POSTGRES_USER:-}" ] && args+=(-U "$POSTGRES_USER")
  if pg_dump "${args[@]}" -f "$OUT/base.dump" 2> "$OUT/pg_dump.err"; then
    n=$(pg_restore --list "$OUT/base.dump" 2>/dev/null | grep -c .)
    [ "$n" -gt 10 ] && ok "base PostgreSQL « $POSTGRES_DB » sauvegardée ($n éléments lisibles dans l'archive)" || ko "archive PostgreSQL suspecte ($n éléments)"
  else ko "pg_dump a échoué (voir $OUT/pg_dump.err)"; fi
  unset PGPASSWORD
  MOTEUR=postgres
else
  SRC=${DJANGO_SQLITE_PATH:-$PROJET/var/db.sqlite3}
  if "$PY" - "$SRC" "$OUT/base.sqlite3" <<'PYEOF'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
a = sqlite3.connect(f"file:{src}?mode=ro", uri=True); b = sqlite3.connect(dst)
a.backup(b); r = b.execute("PRAGMA integrity_check").fetchone()[0]
sys.exit(0 if r == "ok" else 3)
PYEOF
  then ok "base SQLite sauvegardée et intègre (copie cohérente, même pendant que le site tourne)"; else ko "sauvegarde SQLite échouée ou corrompue ($SRC)"; fi
  MOTEUR=sqlite
fi

# 3. Médias (images envoyées) et statiques (reconstruits au démarrage : sauvegardés par prudence seulement si présents).
MEDIA=${DJANGO_MEDIA_ROOT:-$PROJET/var/media}
if [ -d "$MEDIA" ]; then
  tar -czf "$OUT/media.tar.gz" -C "$(dirname "$MEDIA")" "$(basename "$MEDIA")" 2>/dev/null && tar -tzf "$OUT/media.tar.gz" >/dev/null 2>&1 && ok "médias archivés ($(du -sh "$OUT/media.tar.gz" | cut -f1), $(tar -tzf "$OUT/media.tar.gz" | wc -l) fichiers)" || ko "archive des médias échouée ou illisible"
else echo "WARN pas de dossier de médias ($MEDIA)"; fi

# 4. Fichier d'environnement : contient VOISINTERNET_ANON_PEPPER (ne JAMAIS le perdre : sans lui, plus aucun compte anonyme n'est récupérable).
if [ -z "${SANS_ENV:-}" ]; then
  cp "$ENV_FILE" "$OUT/environnement.env" && chmod 600 "$OUT/environnement.env" && ok "fichier d'environnement copié (droits 600 : SECRETS)" || ko "copie du fichier d'environnement échouée"
  grep -q '^VOISINTERNET_ANON_PEPPER=.\+' "$ENV_FILE" && ok "VOISINTERNET_ANON_PEPPER présent dans la copie" || echo "WARN VOISINTERNET_ANON_PEPPER absent ou vide dans $ENV_FILE : à vérifier à la main"
fi

# 5. Nombre d'enregistrements (pour comparer après la mise à jour).
"$PY" manage.py shell -c "
from django.contrib.auth import get_user_model
from core.models import Account, Shortcut, Event, DirectoryEntry
print('comptes', Account.objects.count()); print('comptes_anonymes', Account.objects.filter(user__isnull=True).count()); print('utilisateurs', get_user_model().objects.count())
print('raccourcis', Shortcut.objects.count()); print('evenements', Event.objects.count()); print('fiches_annuaire', DirectoryEntry.objects.count())
" 2>"$OUT/enregistrements.err" | grep -v 'imported automatically' > "$OUT/enregistrements.txt"; [ -s "$OUT/enregistrements.txt" ] && ok "décomptes notés : $(tr '\n' ' ' < "$OUT/enregistrements.txt")" || ko "décompte impossible (voir $OUT/enregistrements.err)"

# 5b. SQLite : la copie contient bien autant de comptes que la base en service (la sauvegarde est lisible, pas seulement « créée »).
if [ "${MOTEUR:-}" = sqlite ]; then
  attendu=$(awk '$1=="comptes"{print $2}' "$OUT/enregistrements.txt")
  copie=$("$PY" -c "import sqlite3,sys; print(sqlite3.connect(sys.argv[1]).execute('select count(*) from core_account').fetchone()[0])" "$OUT/base.sqlite3" 2>/dev/null)
  [ -n "$attendu" ] && [ "$attendu" = "$copie" ] && ok "la copie SQLite contient les $copie comptes de la base en service" || ko "la copie SQLite contient « $copie » comptes, la base en service « $attendu »"
fi

# 6. Sommes de contrôle et récapitulatif.
( cd "$OUT" && sha256sum $(ls | grep -v SHA256SUMS) > SHA256SUMS ) && ok "sommes SHA-256 écrites"
echo; ls -la "$OUT"
echo
if [ "$ko" -eq 0 ]; then
  echo "SAUVEGARDE OK : $OUT"
  echo "À FAIRE MAINTENANT : copier ce dossier HORS de la machine (par exemple : scp -r \"\$USER@<machine>:$OUT\" ~/ ), puis vérifier la copie : cd <copie> && sha256sum -c SHA256SUMS"
else echo "SAUVEGARDE INCOMPLÈTE : ne pas mettre à jour tant qu'un KO subsiste."; fi
exit $ko
