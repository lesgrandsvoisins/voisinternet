# Transition de www.gv.je : cadrage

*Cadrage du 29/10/2026, à trancher par Chris. Rien n'est modifié tant qu'une option n'est pas choisie.*

## Ce qu'est www.gv.je aujourd'hui

Un **tableau de bord Homepage** (service NixOS `homepage-dashboard`, port 8082, derrière Caddy), décrit dans `flakeops`
(`modules/homepage-dashboard.nix` et `modules/homepage-dashboard/*.nix`). Titre : « GV.je Tableau de bord ! ». `gv.je`
redirige vers lui, ainsi que d'autres noms (`dash.gdvoisins.com`…). Il affiche **50 tuiles** réparties en 16 rubriques :
compte unifié, courriel, tâches (Vikunja), fichiers (SFTPGo, Copyparty, Oxicloud, Immich), forum, discussions, listes de
diffusion, dons, sites publics, médias sociaux, administration système (Keycloak, ListMonk, SFTPGo…), et d'anciens
services. Il n'a ni compte, ni personnalisation, ni traduction (français seulement).

Ne pas confondre : le **domaine** `gv.je` porte aussi l'identité (`key.gv.je`, adresses `@gv.je`, `sftpgo.gv.je`,
`memos.gv.je`…). La transition ne concerne que **l'hôte `www.gv.je`** (le tableau de bord), pas ces services.

## Ce que fait déjà www.lesgrandsvoisins.com pour le même besoin

La page **Services et liens** (`/fr/account/raccourcis/`) : catalogue de services par catégorie, liste personnelle « Mes
liens » qui se retrouve sur tous les appareils, services « en attente » d'activation, traduit en 5 langues, accessible
au clavier. **47 des 50 tuiles** correspondent déjà, par nom de domaine, à un service du catalogue de `www`. Il manque
seulement `immich.gv.je`, `vikunja.gv.je` et `wagtail.resdigita.com`.

## Les options

| | Option | Ce qui change | Avantages | Risques / coût |
|---|---|---|---|---|
| **A** | **Remplacer** le tableau de bord par « Services et liens » ; `www.gv.je` redirige vers `www.lesgrandsvoisins.com/fr/account/raccourcis/` | Un seul endroit, une seule liste à tenir ; les membres personnalisent ; 5 langues | Une seule source de vérité ; moins de services à maintenir (Homepage retiré) ; cohérence avec le reste | La page demande un clic de plus pour un accès anonyme ; les tuiles d'administration (Keycloak, ListMonk…) doivent aller ailleurs (voir ci-dessous) ; habitudes des personnes qui ont `www.gv.je` en favori |
| **B** | **Garder** le tableau de bord, mais l'aligner : liens vers les parcours, textes revus, tuiles obsolètes retirées | Rien ne bouge côté adresses | Aucun risque ; rapide | Deux listes de services à tenir en parallèle (déjà 47 sur 50 en double) |
| **C** | **Fusion progressive** : `www.gv.je` devient une page publique de `www` (vue du catalogue sans compte), et le tableau de bord ne sert plus qu'aux administrateurs (nouvelle adresse, accès restreint) | Le public voit le catalogue sans se connecter ; les outils d'administration sortent de la vitrine | Meilleur des deux ; réversible par étapes | Plus de travail (page publique, restriction d'accès côté Caddy / Keycloak) |
| **D** | **Retirer** `www.gv.je` sans remplaçant | — | Rien à maintenir | Casse les favoris et les liens ; déconseillé |

## Ma recommandation : C, en deux temps

1. **Maintenant, sans risque** : ajouter à `www` les 3 services manquants, retirer les tuiles « Anciens services » devenues
   inutiles, et ne **rien rediriger** encore.
2. **Ensuite** : une page publique « Services » sur `www` (catalogue sans connexion, avec « Ouvrir »), puis
   `www.gv.je` → redirection 301 vers cette page. Les tuiles d'administration passent sur un hôte restreint
   (par exemple `admin.gv.je`, derrière Keycloak, groupe « Administration »), ou dans la page d'administration de `www`.

Pourquoi C plutôt que A : un tableau de bord sert deux publics (les membres, qui veulent leurs outils ; les
administrateurs, qui veulent l'administration). `www` sert déjà bien les premiers, pas encore les seconds ; les mélanger
dans une même page, c'est ce qui rend `www.gv.je` difficile à ranger aujourd'hui.

## Décisions à prendre

1. **Option** : A, B, C (recommandée) ou D ?
2. **Tuiles d'administration** (Keycloak, ListMonk, SFTPGo, Ghost…) : où doivent-elles vivre ? (page d'administration de
   `www` réservée au groupe « Administration », hôte restreint, ou rester dans Homepage ?)
3. **« Anciens services »** (Homarr, Copyparty, Vikunja ancien, KeeWeb, Crabfit, Wikijs…) : lesquels sont encore en
   service ? Les autres sont retirés de la liste, pas redirigés.
4. **Redirections des autres noms** (`gv.je`, `dash.gdvoisins.com`, `homepage-dashboard.gv.je`…) : suivent `www.gv.je`
   (recommandé) ou restent à part ?
5. **Calendrier** : avant ou après le retrait de `old.lesgrandsvoisins.com` ?

## Ce que je peux faire sans attendre

- Écrire la comparaison **tuile par tuile / service par service** (fichier prêt à relire) et les 3 services à ajouter.
- Préparer la page publique « Services » de `www` (option C, étape 2) sans la brancher.
- Rédiger la demande à l'administration (Caddy) pour la redirection, **à n'appliquer qu'après votre décision**.

*Hors périmètre sans demande de l'administration :* toute modification de `flakeops` hors des branches `ux/…`, de
Keycloak ou de Caddy.
