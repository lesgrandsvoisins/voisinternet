# Transition de www.gv.je : plan (décisions du 30/10/2026)

> **Mise à jour du 30/10 (après-midi) :** décision de Chris : *« www.resdigita.com peut reprendre ce qui est aujourd'hui sur www.gv.je »*. `www.resdigita.com` sert donc, côté serveur, **le même tableau de bord Homepage** que `www.gv.je` (port 8082, en parallèle ; `www.gv.je` n'est pas touché), et le site Wagtail qui s'y trouvait est sous `www.libregood.com`. **Le tableau de bord de `voisinternet` (`/outils/`, `OUTILS_HOSTS`) est donc mis de côté** : le code reste en place, inactif ; ne PAS poser `VOISINTERNET_OUTILS_HOSTS` ni ajouter `www.resdigita.com` aux hôtes de Django tant que Chris n'a pas dit que `voisinternet` remplace Homepage sur ce nom. Les étapes (a) à (c) du tableau ci-dessous ne sont plus d'actualité ; les 301 de `www.gv.je` et `gv.je` vers `www.resdigita.com` viendront quand Chris le dira.

## Décisions prises

1. **Deux noms, deux rôles.** `lesgrandsvoisins.com` : le nom public, qu'on dit à voix haute (marque, site, blog, agenda,
   annuaire). **`resdigita.com`** : le domaine « côté ordinateur » (outils, tableau de bord, connexion, adresses de
   courrier). Décision de l'association, confirmée par Chris.
2. **`gv.je` n'est pas mémorable** : il cesse d'être le nom mis en avant. Il reste une **adresse alias** (les boîtes déjà
   créées gardent `@gv.je`) et ses anciens liens redirigent ; rien ne casse.
3. **`www.gv.je` a une fonction à garder : le tableau de bord** de l'ensemble des outils, ce qui manque sur
   `lesgrandsvoisins.com`. Il est repris par `voisinternet`, au domaine des outils.

## Ce que le tableau de bord devient

La même application (`voisinternet`) sert les deux noms. Sur `www.resdigita.com`, la page d'accueil est le **tableau de
bord des outils** (`/fr/outils/`) : grille compacte par catégorie, un clic pour ouvrir, **sans connexion** ; si la
personne est connectée, ses services (« Mes services ») sont rappelés en tête ; les outils d'administration (Keycloak,
ListMonk, SFTPGo…) n'apparaissent qu'au groupe « Administration ». Le reste (compte, services, connexion) fonctionne à
l'identique sur les deux noms.

## Fait dans le code (voisinternet, prêt, inactif)

- Page `/outils/` (tableau de bord), tuiles compactes, traduite en 5 langues.
- Réglage `VOISINTERNET_OUTILS_HOSTS` (liste de noms de domaine) : sur ces noms, `/fr/`, `/en/`… affichent le tableau de
  bord. Vide par défaut : aucun effet.
- Champ « réservé à l'administration » sur chaque service (administration, migration 0038) ; masqué du public dans le
  tableau de bord, le catalogue, l'accueil, la recherche et les étiquettes.

## À faire, dans l'ordre

| # | Étape | Qui | Remarque |
|---|---|---|---|
| 1 | **Ajouter au catalogue les 3 outils manquants** (`immich.gv.je`, `vikunja.gv.je`, `wagtail.resdigita.com`) et **cocher « réservé à l'administration »** sur Keycloak, ListMonk, SFTPGo (admin), Ghost (admin) | Chris, dans `/admin/` (ou moi sur demande) | 47 des 50 tuiles de Homepage sont déjà dans le catalogue |
| 2 | **Décider du sort des « anciens services »** (Homarr, Copyparty, Vikunja ancien, KeeWeb, Crabfit, Wikijs…) : lesquels sont encore en service ? Les autres sortent du catalogue | Chris | Se règle en décochant « proposé » |
| 3 | **Site actuel de `www.resdigita.com`** : décidé par Chris le 30/10 : son contenu migre vers `libregood.com` (le site Wagtail est servi SOUS `www.libregood.com`, sans redirection) ; ensuite `gv.je` passe à `resdigita.com`, qui prend tout de suite son nouveau rôle d'outils. Ordre d'exécution exact : `docs/MIGRATION-resdigita-libregood.md` de `flakeops` (branche `rosest330`) | Chris + administration | L'administration attend le « go » de Chris pour chaque étape ; **aucune action côté `voisinternet`** tant que le serveur n'est pas prêt |
| 4 | **Serveur** : `www.resdigita.com` pointe vers `voisinternet` (comme `www.lesgrandsvoisins.com`), `DJANGO_ALLOWED_HOSTS` et `DJANGO_CSRF_TRUSTED_ORIGINS` complétés, `VOISINTERNET_OUTILS_HOSTS=www.resdigita.com`, adresses de retour de connexion et de déconnexion déclarées dans le client Keycloak (`https://www.resdigita.com/*`) | Administration (demande n°16) | Une seule application, deux noms |
| 5 | **Redirections 301** de `www.gv.je`, `gv.je` et des autres noms de l'ancien tableau de bord (`dash.gdvoisins.com`…) vers `https://www.resdigita.com/` | Administration | Après vérification de l'étape 4 |
| 6 | **Arrêter Homepage** (service `homepage-dashboard`, port 8082) après quelques semaines | Administration | Les tuiles sont conservées dans `flakeops` (historique) |
| 7 | **Courrier** : proposer `@resdigita.com` comme adresse (le domaine est déjà hébergé pour le courrier) ; `@gv.je` reste valable | Chris + administration | Décision séparée, touche Keycloak et le courrier |

## Ce qui est perdu avec Homepage, à savoir

Le tableau de bord actuel affiche aussi des **widgets** (agenda, mémos « Twitter des GV », météo) et une barre de titre
propre. Les tuiles d'outils se retrouvent toutes ; l'agenda existe déjà sur `lesgrandsvoisins.com`. Les mémos
(`memos.gv.je`) restent atteignables comme outil, pas comme flux dans la page.

## Points de vigilance

- **Connexion sur deux noms** : `www.resdigita.com` et `www.lesgrandsvoisins.com` sont deux sites pour le navigateur,
  donc deux sessions. Grâce à Keycloak (une seule connexion unique), la deuxième connexion est immédiate, sans mot de
  passe redemandé.
- **Marque** : `resdigita` et `lesartsvoisins` évitent de rapprocher le domaine d'outils de la marque d'origine du site
  de Saint-Vincent-de-Paul ; pour tout nom contenant « grands voisins », une vérification auprès de l'INPI/EUIPO est
  prudente avant d'en faire un domaine principal.
- **Courrier** : un domaine déjà en usage pour le courrier (`resdigita.com`) a une réputation à entretenir (voir B-011).
