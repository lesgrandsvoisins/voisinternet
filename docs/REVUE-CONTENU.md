# Revue de contenu

*But : décider, page par page, ce qui reste, ce qui est fusionné, ce qui est retiré, ce qui est corrigé, avant de fermer
l'ancien site et de redirigir les anciens noms. Préparé le 29/10/2026.*

## 1. L'outil

Sur le serveur (conteneur `voisinter-django`) :

```sh
deploy/manage.sh inventaire_contenu --sortie /tmp/revue --liens
```

Il produit, sans rien modifier :
- **`inventaire.csv`** : une ligne par page, billet, évènement, fiche d'annuaire et service (type, titre, adresse, langue,
  statut, dates, longueur du texte, images, traductions, liens vers les anciens sites, **alertes**), avec les colonnes
  vides **décision** et **remarque** pour les relecteurs. À ouvrir dans un tableur et à partager.
- **`resume.md`** : décompte par alerte, avec des exemples.

Il ne contient aucune donnée personnelle (pas de courriel ni de téléphone). Les fiches d'annuaire non publiques sont
signalées sans leur texte.

### Alertes

| Alerte | Sens |
|---|---|
| `brouillon` / `non-publié` / `non-publique` | pas visible du public : à publier ou à abandonner |
| `texte-court` | moins de 150 caractères (80 pour une fiche) : vide, ou page-index sans intérêt |
| `sans-image-de-une` | billet, projet, pôle ou évènement sans image d'en-tête |
| `sans-description` | pas de description pour les moteurs de recherche |
| `lien-ancien-site` | lien vers `old`, `blog` ou `lesgrandsvoisins.fr` (à remplacer ou à reprendre) |
| `image-sans-texte-alternatif` | image sans description pour les lecteurs d'écran |
| `traductions-manquantes` | page française d'une rubrique sans les 4 autres langues |
| `titre-en-double` | deux pages publiées avec le même titre (doublon probable) |
| `lien-interne-cassé(…)` | un lien du site ne répond pas (avec `--liens`) |

## 2. Qui relit quoi

| Qui | Quoi |
|---|---|
| **Chris** | le fond : exactitude, ton, ce qui reste, ce qui est retiré ; textes juridiques (intérêt général, coopérative, statuts) ; fiches de l'équipe |
| **Relecteurs arabe / coréen** | les libellés du site et les pages traduites (BACKLOG U-021) |
| **Personnes citées** | leur fiche d'annuaire et leur photo (consentement), page d'équipe |
| **Claude (session UX)** | appliquer les décisions (dépublier, fusionner, reclasser, redirections), corriger liens et images |

## 3. Critères (pour chaque ligne)

1. **Juste** : l'information est-elle encore vraie (dates, lieux, noms, montants) ?
2. **Utile** : quelqu'un la cherche-t-il ? Est-elle déjà ailleurs dans le site (doublon) ?
3. **À sa place** : billet de blog (daté, journal) ou page (permanente) ? Dans la bonne rubrique ?
4. **Consentement** : personnes nommées ou photographiées, coordonnées publiées, IBAN ; rien de privé.
5. **Accessible** : titres ordonnés, liens explicites (pas « cliquez ici »), images avec texte alternatif, contraste.
6. **Traduit** : au moins le français ; les rubriques principales dans les cinq langues.
7. **Relié** : aucun lien vers un ancien site, aucun lien cassé.

## 4. Décisions possibles (colonne « décision »)

`garder` · `corriger` (préciser dans « remarque ») · `fusionner avec <adresse>` · `déplacer vers <rubrique>` ·
`retirer` (dépublier ; jamais supprimer sans accord) · `à traduire` · `à faire relire par <nom>`

## 5. Déroulé proposé

1. Lancer l'inventaire (ci-dessus), partager `inventaire.csv`.
2. **Tri rapide** (Chris, 1 heure) : parcourir les alertes, remplir « décision » pour les pages évidentes
   (doublons, brouillons à abandonner, pages vides).
3. **Lots de relecture** par rubrique : Association → Blog → Pôles → Annuaire → Agenda → Services.
4. **Application** des décisions par Claude (commandes de reclassement et de redirection, avec simulation d'abord),
   puis nouvelle exécution de l'inventaire pour vérifier que les alertes baissent.
5. **Arrêt de l'ancien site** quand les redirections de `old` et du blog Ghost sont en service et que le CSV ne
   montre plus de `lien-ancien-site`.

## 6. Déjà repéré (avant même l'inventaire)

- **27 pages Ghost** importées comme billets de blog : à reclasser (voir `docs/…` / message du 29/10) ; seules les
  12 Gazettes devraient rester des billets.
- **Liens d'anciens PDF** (3 billets) introuvables ; **PDF des statuts** à relier ; **16 images d'en-tête** de pages Ghost
  en attente des fichiers.
- **Équipe** : photos et noms à confirmer avec les personnes.
- **Textes juridiques** (intérêt général, coopérative) : à faire relire avant publication ; **IBAN** de la page Dons de
  Ghost : à confirmer.
- **Arabe et coréen** : relecture native.
