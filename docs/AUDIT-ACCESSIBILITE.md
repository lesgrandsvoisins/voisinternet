# Audit d'accessibilité (30/10/2026)

**Méthode.** Contrôle automatique avec axe-core (WCAG 2.0, 2.1 et 2.2, niveaux A et AA, plus les bonnes pratiques) de
18 pages clés (accueil en fr/ar/en, compte, services, parcours, groupes, agenda, annuaire, blog, contact, association,
outils, recherche, étiquettes, mes fiches, mes évènements), en thème clair et sombre, en 1280 et 390 px, avec un compte.
Plus des vérifications à la main par script : lien d'évitement, indicateur de focus sur 40 tabulations, débordement
horizontal à 320 px (équivalent d'un zoom 400 %), structure des titres, langue et sens de lecture. Script :
`tools/audit_accessibilite.js`.

## Résultat
**Avant : 38 violations. Après les corrections : 0.** Ce qui est contrôlé automatiquement ne couvre qu'environ un tiers
des critères : la section « Reste à faire » dit ce qui demande une personne.

## Corrigé
| Problème | Où | Correction |
|---|---|---|
| Contraste 1,8:1 (blanc sur jaune) | pastille de date de l'agenda | texte foncé |
| Contraste 1,8:1 (texte à 35 % d'opacité) | jours des mois voisins du calendrier | le fond les distingue, plus la transparence |
| Cible tactile de 16 px | points d'évènements du calendrier (accueil, agenda) | 24 px |
| Contrôle interactif imbriqué | liens « Ajouter un service / Rejoindre un groupe / … » dans le résumé repliable de « Mon compte » | les liens sortent du résumé (ils le surplombent) |
| Lien masqué (`aria-hidden`) mais focalisable | liste des évènements | `tabindex="-1"` (le titre porte déjà le lien) |
| Ordre des titres (h1 puis h3) | annuaire vide | h2 |
| Cible tactile de 23,6 px | liens « Ajouter… » | 24 px minimum |
| Débordement horizontal à 320 px | champ de recherche du blog | le champ rétrécit et passe à la ligne |
| Focus peu visible (contour supprimé) | champ de recherche du blog | contour de 3 px |
| Cible du lien d'évitement | `<main>` | `tabindex="-1"` : le focus arrive bien sur le contenu |
| Code en ligne qui élargit la page | pages avec code | retour à la ligne |

## Déjà bon (constaté)
- Lien d'évitement « Aller au contenu » en première tabulation, qui fonctionne.
- Indicateur de focus visible sur chaque élément tabulé (accueil, compte, services).
- Un seul `h1` par page, un seul `main`, titres de page distincts, `lang` et `dir` corrects (arabe de droite à gauche).
- Sélecteur de langue avec `lang` / `hreflang` ; messages dans une zone `role="status" aria-live="polite"`.
- Pas de débordement horizontal à 320 px sur les pages testées ; `prefers-reduced-motion` respecté.
- Réordonner les services au clavier : boutons ↑ ↓ (le glisser-déposer n'est qu'un confort).

## Reste à faire (demande une personne ou un autre outil)
1. **Lecteur d'écran** (NVDA, VoiceOver, TalkBack) : parcours de l'accueil, de « Mon compte », de l'inscription et du
   formulaire d'une fiche ; ordre de lecture, annonces des changements dynamiques (htmx), noms des boutons.
2. **Arabe et coréen** : ordre visuel de droite à gauche des icônes de l'en-tête, des fils d'Ariane et des tableaux ;
   à relire avec un lecteur natif (voir BACKLOG U-021).
3. **Formulaires avec erreurs** : message d'erreur relié au champ (`aria-describedby`), focus ramené sur le résumé des
   erreurs ; à tester avec des erreurs réelles (fiche, évènement, contact).
4. **Contenu éditorial** : textes alternatifs des images du blog et de l'ancien site (voir l'inventaire de contenu,
   alerte « image-sans-texte-alternatif »), liens explicites (« cliquez ici »), titres dans l'ordre.
5. **Pages servies par d'autres applications** (Keycloak, Wagtail `/cms/`, Wiki.js, outils) : hors périmètre de ce site ;
   l'écran de connexion et d'inscription Keycloak (thème `gv-registration`) mérite le même contrôle.
6. **Déclaration d'accessibilité** (obligatoire pour un organisme public, utile à tous) : à rédiger après le point 1.
