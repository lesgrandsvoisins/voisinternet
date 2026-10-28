# Changelog

Changements notables de `www.lesgrandsvoisins.com` (voisinternet), branche de travail UX. Format inspiré de *Keep a Changelog* ; rubriques *Added*, *Changed*, *Fixed*, *Security*, *Removed*, contenu en français. Les décisions et ce qui reste à faire sont dans [BACKLOG.md](BACKLOG.md). Les besoins côté serveur passent par `docs/DEMANDES-UX.md` du dépôt `chris2fr/flakeops` (branche `ux/demandes-ux`).

## [Unreleased]
### Added
- **Parcours guidés** (`/account/parcours/`) : petites missions pédagogiques (étapes cochables ou détectées d'après le compte, « Pourquoi ? » dépliable, barre de progression, félicitations), éditables et traduisibles dans l'administration (`Mission`, `MissionStep`, `StepCompletion`). Trois parcours d'exemple : premiers pas, boîte courriel, relecture des traductions arabe et coréen via Vikunja. Entrée « Parcours guidés » dans le menu.
### Changed
- Identifiant de connexion : les textes décrivent la nouvelle règle (5+5 lettres, numéro seulement si pris) ; le parcours « Ma boîte courriel » est **masqué** (fixtures : `active: false`) tant que les nouveaux comptes n'ont pas d'adresse de courrier (`B-039`).
- Outil `tools/export_contenu.py` : extraction du contenu public (pages Wagtail, redirections, agenda, annuaire public) en JSON Lines, pour comparer `old`, `www` et le blog. `deploy/smoke.sh` et `docs/DEPLOIEMENT.md` (brouillon).
- `deploy/sauvegarde.sh` (base, médias, environnement dont `VOISINTERNET_ANON_PEPPER`, vérifiée) et `deploy/mise-a-jour.sh` (garde-fous, essai à blanc, retour arrière) ; `docs/DEPLOIEMENT.md` réécrit avec restauration. Essayés en simulation locale seulement. Le dépôt est privé : le code et les scripts se livrent par `git bundle` (docs/DEPLOIEMENT.md, 0a).
### Fixed
- Scripts de déploiement : le fichier d'environnement (format systemd) était lu comme un script shell, ce qui échouait dès qu'une valeur contenait un « $ » (`unbound variable`) ; il est maintenant chargé sans interprétation (`charger_env`). Défaut vu au premier essai sur le serveur.
- Parcours courriel et Vikunja : retiré ce qui n'est pas vérifié (connexion de Vikunja par `key.gv.je`, libellé « Indésirables » seul) ; la relecture ar/ko dit maintenant « demandez-nous un accès ».
- En arabe (droite à gauche), les groupes de chiffres du numéro de compte anonyme s'affichaient à l'envers : le numéro est maintenant toujours lu de gauche à droite.
- Interface des parcours guidés traduite en en/es/ar/ko (le contenu des parcours reste en français tant qu'il n'est pas traduit dans l'administration).
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
