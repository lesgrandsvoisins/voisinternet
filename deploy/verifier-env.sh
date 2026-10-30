#!/usr/bin/env bash
# Vérifie le fichier d'environnement du service SANS afficher un seul secret : les réglages non secrets sont montrés avec
# leur valeur, tout le reste (clé, mot de passe, jeton, secret, poivre…) seulement « défini » et sa longueur.
# Signale aussi les erreurs courantes d'un fichier au format systemd (EnvironmentFile) : ligne sans « = », espaces autour de
# « = », guillemets non fermés, clé en double (la dernière gagne), « $ » dans une valeur.
# Usage (dans le conteneur) :  deploy/verifier-env.sh [FICHIER]      (défaut : /etc/voisinter-django/voisinter-django.env)
f=${1:-${ENV_FILE:-/etc/voisinter-django/voisinter-django.env}}
[ -r "$f" ] || { echo "Fichier illisible : $f" >&2; exit 2; }
declare -A vu; ko=0; avert=0
SECRET='SECRET|PASSWORD|PASSWD|PEPPER|TOKEN|KEY|PRIVATE|CREDENTIAL'
NONSECRET='^(DJANGO_ALLOWED_HOSTS|DJANGO_CSRF_TRUSTED_ORIGINS|DJANGO_DEBUG|DJANGO_BASE_URL|DJANGO_IP|DJANGO_PORT|DJANGO_MEDIA_ROOT|KEYCLOAK_REALM_URL|OIDC_RP_CLIENT_ID|POSTGRES_DB|POSTGRES_HOST|POSTGRES_USER|EMAIL_HOST|EMAIL_PORT|EMAIL_HOST_USER|DEFAULT_FROM_EMAIL|VOISINTERNET_[A-Z_]*)$'
n=0
while IFS= read -r l || [ -n "$l" ]; do
  n=$((n+1))
  case "$l" in ''|'#'*|';'*) continue;; esac
  if [[ "$l" != *=* ]]; then echo "KO   ligne $n : pas de « = » (ignorée par systemd)"; ko=1; continue; fi
  k=${l%%=*}; v=${l#*=}
  [[ "$k" =~ [[:space:]]$ || "$v" =~ ^[[:space:]] ]] && { echo "AVERT ligne $n ($k) : espace autour de « = » (comportement variable selon la version de systemd)"; avert=1; }
  k=${k#export }; k=${k// /}
  [[ "$k" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || { echo "KO   ligne $n : nom de variable invalide"; ko=1; continue; }
  [ -n "${vu[$k]:-}" ] && { echo "AVERT $k défini deux fois (lignes ${vu[$k]} et $n : la dernière gagne)"; avert=1; }
  vu[$k]="$n"
  case "$v" in \"*[!\"]|\'*[!\']) echo "KO   ligne $n ($k) : guillemet non fermé"; ko=1;; esac
  case "$v" in *'$'*) echo "AVERT $k : contient « \$ » (littéral dans un fichier systemd, pas une variable)"; avert=1;; esac
  case "$v" in \"*\") v=${v#\"}; v=${v%\"};; \'*\') v=${v#\'}; v=${v%\'};; esac
  if [[ "$k" =~ $SECRET ]] && ! [[ "$k" =~ ^(VOISINTERNET_(REDIRECTIONS|DECONNEXION_KEYCLOAK|ANON_ACCOUNTS)|KEYCLOAK_REALM_URL)$ ]]; then
    printf '  %-40s = (secret : %s caractères)\n' "$k" "${#v}"
  elif [[ "$k" =~ $NONSECRET ]]; then
    printf '  %-40s = %s\n' "$k" "$v"
  else
    printf '  %-40s = (défini, %s caractères)\n' "$k" "${#v}"
  fi
  case "$k" in VOISINTERNET_ANON_PEPPER) pepper=$v;; DJANGO_ALLOWED_HOSTS) hotes=$v;; DJANGO_CSRF_TRUSTED_ORIGINS) origines=$v;; esac
done < "$f"
echo "--- Contrôles"
[ "${vu[VOISINTERNET_ANON_PEPPER]:-}" ] && [ -z "$pepper" ] && echo "AVERT VOISINTERNET_ANON_PEPPER est VIDE : pepper vide (pas de repli sur la clé secrète). Ne PAS le remplir si des comptes anonymes existent."
[[ "${hotes:-}" == *"["* || "${hotes:-}" == *"]("* ]] && { echo "KO   DJANGO_ALLOWED_HOSTS contient des crochets/lien Markdown"; ko=1; }
for k in DJANGO_SECRET_KEY DJANGO_ALLOWED_HOSTS DJANGO_CSRF_TRUSTED_ORIGINS VOISINTERNET_ANON_PEPPER KEYCLOAK_REALM_URL OIDC_RP_CLIENT_ID OIDC_RP_CLIENT_SECRET; do
  [ -n "${vu[$k]:-}" ] && echo "OK   $k présent" || { echo "KO   $k ABSENT"; ko=1; }
done
for h in www.lesgrandsvoisins.com; do [[ ",${hotes:-}," == *",$h,"* ]] && echo "OK   $h dans DJANGO_ALLOWED_HOSTS" || { echo "KO   $h absent de DJANGO_ALLOWED_HOSTS"; ko=1; }; done
for h in www.resdigita.org; do [[ ",${hotes:-}," == *",$h,"* ]] && echo "INFO $h est dans DJANGO_ALLOWED_HOSTS (prêt pour le tableau de bord)" || echo "INFO $h n'est pas encore dans DJANGO_ALLOWED_HOSTS"; done
for o in https://www.lesgrandsvoisins.com; do [[ ",${origines:-}," == *",$o,"* ]] && echo "OK   $o dans DJANGO_CSRF_TRUSTED_ORIGINS" || echo "AVERT $o absent de DJANGO_CSRF_TRUSTED_ORIGINS"; done
[[ ",${origines:-}," == *",https://www.resdigita.org,"* ]] && echo "INFO https://www.resdigita.org est dans DJANGO_CSRF_TRUSTED_ORIGINS" || echo "INFO https://www.resdigita.org n'est pas encore dans DJANGO_CSRF_TRUSTED_ORIGINS"
IFS=',' read -ra lst <<< "${origines:-}"; for o in "${lst[@]}"; do [[ -z "$o" || "$o" == https://* ]] || { [[ "$o" =~ ^http://(192\.168|10\.|127\.)[0-9.]*$ ]] && echo "INFO origine CSRF http:// sur adresse interne : $o (normal)" || { echo "KO   origine CSRF sans https:// : $o"; ko=1; }; }; done
echo "--- $([ $ko -eq 0 ] && echo 'Aucune erreur' || echo 'ERREURS à corriger')$([ $avert -eq 1 ] && echo ', avec des avertissements')"
exit $ko
