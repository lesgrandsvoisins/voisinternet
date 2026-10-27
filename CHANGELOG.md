# Changelog

Changements notables de `www.lesgrandsvoisins.com` (voisinternet), branche de travail UX. Format inspiré de *Keep a Changelog* ; rubriques *Added*, *Changed*, *Fixed*, *Security*, *Removed*, contenu en français. Les décisions et ce qui reste à faire sont dans [BACKLOG.md](BACKLOG.md). Les besoins côté serveur passent par `docs/DEMANDES-UX.md` du dépôt `chris2fr/flakeops` (branche `ux/demandes-ux`).

## [Unreleased]
### Added
- **Parcours guidés** (`/account/parcours/`) : petites missions pédagogiques (étapes cochables ou détectées d'après le compte, « Pourquoi ? » dépliable, barre de progression, félicitations), éditables et traduisibles dans l'administration (`Mission`, `MissionStep`, `StepCompletion`). Trois parcours d'exemple : premiers pas, boîte courriel, relecture des traductions arabe et coréen via Vikunja. Entrée « Parcours guidés » dans le menu.
### Changed
- Test d'inscription dans un navigateur écrit côté `flakeops` (branche `ux/test-inscription-navigateur`, non vérifié, jamais lancé).
- Taches décoratives de l'accueil atténuées sur petit écran (contraste du texte d'introduction).
- Liste « Premiers pas » en puces ; lien vers les parcours guidés.

## 2026-10-27
### Added
- Onboarding (plan : `docs/ONBOARDING.md`) :
  - bandeau du numéro de compte anonyme, conservé sur toutes les pages jusqu'à confirmation (copier, télécharger en `.txt`, « J'ai noté mon numéro ») ;
  - parcours distincts « Créer mon compte » / « J'ai déjà un compte » / « Rester anonyme » (page « Mon compte », panneau d'en-tête, accueil selon l'état de la personne) ;
  - vues `core:inscription` et `core:connexion` : départ vers Keycloak dans la langue du site (`ui_locales`, `kc_locale`), `prompt=create` pour l'inscription ;
  - identifiant de connexion Keycloak (`preferred_username`) montré à la première connexion et dans « Mon profil » ;
  - liste « Premiers pas » cochée d'après les données du compte ;
  - retour explicite sur « Mon compte » quand la connexion Keycloak échoue.
- Sélecteur de langue en pied de page, sans JavaScript.
- Agenda : aperçu de l'évènement avec son statut pour les responsables ; courriel au groupe « Administration » à la création, courriel aux responsables à la publication.
- Traductions en/es/ar/ko des nouveaux textes.
- `.env.example` : royaume Keycloak `master`.
### Changed
- Noms accessibles (`aria-label`, `title`) sur les icônes de l'en-tête ; les liens du pied de page ne s'ouvrent plus dans un nouvel onglet.
- « Mes évènements » : le formulaire de création passe en tête de page ; le statut devient une pastille.
### Fixed
- Consulter « Mes évènements » créait un compte anonyme : il n'est plus créé qu'à l'envoi du formulaire.
- Le lien d'inscription Keycloak appelait `/protocol/openid-connect/registrations` sans `response_type` : remplacé par la vue `core:inscription`.
- Le numéro du compte anonyme n'était affiché qu'une fois, puis perdu.
### Security
- Le numéro du compte anonyme reste en session (non chiffrée côté serveur) jusqu'à confirmation ; il est effacé à la confirmation. Seule son empreinte est stockée en base.
