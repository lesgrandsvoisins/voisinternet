#!/usr/bin/env bash
# Test de fumée de www.lesgrandsvoisins.com après un déploiement (lecture seule : des GET, aucun compte créé).
# Usage : deploy/smoke.sh [URL_DE_BASE]   (défaut : https://www.lesgrandsvoisins.com)
# Sans DNS : deploy/smoke.sh http://127.0.0.1:8091 avec HOST=www.lesgrandsvoisins.com
# Sortie : une ligne OK/KO par contrôle ; code de retour non nul s'il y a un KO.
BASE=${1:-https://www.lesgrandsvoisins.com}; BASE=${BASE%/}
HOST_HDR=()
[ -n "${HOST:-}" ] && HOST_HDR=(-H "Host: $HOST")
ko=0
verif() { # verif DESCRIPTION CHEMIN STATUT_ATTENDU [TEXTE_ATTENDU_DANS_LA_REPONSE_OU_L_ENTETE]
  local desc=$1 chemin=$2 attendu=$3 texte=${4:-} sortie code
  sortie=$(curl -s -i -m 20 "${HOST_HDR[@]}" "$BASE$chemin") || { echo "KO   $desc : pas de réponse"; ko=1; return; }
  code=$(printf '%s' "$sortie" | head -1 | awk '{print $2}')
  if [ "$code" != "$attendu" ]; then echo "KO   $desc : HTTP $code (attendu $attendu)"; ko=1; return; fi
  if [ -n "$texte" ] && ! printf '%s' "$sortie" | grep -qiF -- "$texte"; then echo "KO   $desc : « $texte » absent"; ko=1; return; fi
  echo "OK   $desc"
}
verif "accueil (fr)"                      /fr/                          200 "Mon compte\|compte"
verif "accueil (ar, droite à gauche)"     /ar/                          200 'dir="rtl"'
verif "mon compte"                        /fr/account/                  200 "Créer mon compte"
verif "parcours guidés"                   /fr/account/parcours/         200 "Parcours guidés"
verif "parcours : détail (courriel)"      /fr/account/parcours/courriel/ 200 "Ma boîte courriel"
verif "agenda"                            /fr/agenda/                   200
verif "mes évènements (sans compte)"      /fr/agenda/mes-evenements/    200
verif "annuaire"                          /fr/annuaire/                 200
verif "inscription -> Keycloak"           /fr/account/inscription/      302 "prompt=create"
verif "inscription : langue transmise"    /es/account/inscription/      302 "ui_locales=es"
verif "connexion -> Keycloak"             /fr/account/connexion/        302 "/protocol/openid-connect/auth"
verif "pied de page : sélecteur de langue" /fr/                         200 'class="foot-lang"'
verif "numéro anonyme : pas de téléchargement sans compte" /fr/account/anonyme/numero/ 404
[ "$ko" -eq 0 ] && echo "Tout est OK." || echo "Au moins un KO."
exit $ko
