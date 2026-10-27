# Plan directeur de l'accueil des nouvelles personnes (onboarding)

Objectif : qu'une personne qui arrive sur lesgrandsvoisins.com comprenne en moins d'une minute ce
qu'elle peut faire, choisisse sans hésiter entre compte nommé et compte anonyme, et ne perde
jamais rien en route. Le site reste utilisable sans JavaScript, sans service tiers, sans traceur.

## Constats (audit du 27/10)

1. **Le numéro du compte anonyme se perd.** Il est affiché une seule fois (`session.pop`), puis
   « ne sera plus jamais affiché ». Un rafraîchissement, un clic ailleurs ou un onglet fermé et le
   compte est irrécupérable. C'est le pire défaut du parcours.
2. **Se connecter et créer un compte sont confondus.** Un seul bouton « se Connecter ou Créer son
   compte » ; le bouton « Créer un compte » est commenté dans `account_panel_body.html`.
3. **Le lien d'inscription Keycloak est cassé.** `keycloak_register_url` appelle
   `/protocol/openid-connect/registrations` sans `response_type` ni `scope` : Keycloak le refuse.
4. **La langue n'est pas transmise à Keycloak.** Le visiteur lit le site en espagnol, l'écran
   d'inscription s'affiche dans la langue du navigateur (et le thème `gv-key-registration` n'a que
   `messages_en.properties`).
5. **Aucune explication des bénéfices.** Rien ne dit ce que donne un compte (raccourcis, groupes,
   fiche d'annuaire, évènements, dons) ni la différence entre nommé et anonyme.
6. **Après la création, rien ne guide.** Un compte vide, quatre compteurs à zéro.
7. **Un échec de connexion Keycloak renvoie sur une page sans explication.**

## Phases

### Phase 1 — Ne jamais perdre le numéro (fait)
- Le numéro reste en session jusqu'à confirmation explicite (« J'ai noté mon numéro »).
- Bandeau visible sur toutes les pages tant qu'il n'est pas confirmé : copier, télécharger (.txt),
  confirmer.
- Le texte « ne sera plus jamais affiché » n'apparaît qu'une fois la confirmation faite.

### Phase 2 — Un choix clair à l'arrivée (fait)
- Trois parcours distincts sur « Mon compte » : *Créer mon compte*, *J'ai déjà un compte*,
  *Rester anonyme*, chacun avec ce qu'il implique en une phrase.
- Boutons *Créer un compte* / *Se connecter* dans le panneau de compte de l'en-tête.

### Phase 3 — Passage propre vers Keycloak (fait côté voisinternet)
- Vues `core:connexion` et `core:inscription` : transmettent `ui_locales`/`kc_locale` (langue du
  site) et, pour l'inscription, `prompt=create` (Keycloak ≥ 24 ouvre directement le formulaire
  d'inscription). Le lien cassé `/registrations` disparaît.
- Échec de connexion : retour sur « Mon compte » avec un message clair.
- Royaume en production : **`master`** (Keycloak 26.8.1), inscription libre, courriels de vérification
  et de réinitialisation actifs (SMTP `mail.lesgrandsvoisins.com`). Voir `docs/HANDOFF-UX.md` de
  `flakeops@rosest330`. L'identifiant (`famille[:4]+prénom[:4]+compteur@gv.je`) est montré à la
  personne à sa première connexion et dans « Mon profil ».
- Messages du thème Keycloak `gv-key-registration` en fr/es/ar/ko (erreurs manquantes et doublons
  de courriel comprises) : écrits, commit `01d42c3` dans le clone de `flakeops`, **pas encore
  poussés ni déployés** ; arabe et coréen à faire relire.
- **À décider :** le compteur d'identifiant qui commence à 2 (`dupojean2@gv.je`) est-il voulu ?

### Phase 4 — Premiers pas (fait)
- Liste « Premiers pas » sur « Mon compte » : ajouter un raccourci, rejoindre un groupe, créer
  une fiche d'annuaire, et pour un compte anonyme, rattacher un compte nommé. Cochée
  automatiquement d'après les données, sans suivi ni stockage supplémentaire.

### Phase 5 — À prévoir
- Page d'accueil : une phrase et un bouton principal selon l'état (visiteur / anonyme / nommé).
- Écran de succès après la première connexion nommée (bienvenue + proposition de rattacher un
  compte anonyme resté sur l'appareil).
- Courriel de bienvenue envoyé par Keycloak (contenu à écrire).
- Accessibilité : parcours complet au clavier, lecteur d'écran, arabe (RTL), `prefers-reduced-motion`.
- Mesure sans traceur : compter côté serveur (création de comptes par type) pour juger l'effet.

## Principes
- Aucune dépendance externe ajoutée ; tout fonctionne sans JavaScript, htmx/Alpine en confort.
- Les chaînes sont en français (langue source) puis traduites via `make messages`.
- Chaque phase a ses tests dans `core/tests.py`.
