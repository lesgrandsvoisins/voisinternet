# Backlog

Ce qui reste à faire pour `www.lesgrandsvoisins.com`, avec **qui** doit agir : *UX* (cette session), *Admin* (session d'administration des serveurs, dépôt `chris2fr/flakeops`), *Chris*. Ce qui est fait est dans [CHANGELOG.md](CHANGELOG.md). Tout ce qui n'est pas vérifié sur le vrai serveur est marqué **non vérifié**.

## Décisions attendues de Chris
1. **Identifiant** : garder l'identifiant généré (`famille[:4]+prénom[:4]+compteur@gv.je`) ou en laisser choisir un ? Pistes en discussion : identifiant de connexion généré et stable (une personne, un identifiant lié à son nom), plus une adresse choisie, par exemple `monchoix@gv.coop`, comme alias sur la même boîte. Compteur qui commence à 2 (`dupojean2`) : voulu ?
2. **Logo du pied de page** : il affiche « new.LesGrandsVoisins.com » (`partials/wordmark.html`) alors que `www` a remplacé `new`. Remplacer par « www. » ou retirer le préfixe ?
3. **« Mark for documents »** : à préciser (relecture de documents ? marquage ? Markdown ?) pour en faire un parcours guidé.
4. **Blog** : `blog.lesgrandsvoisins.com` doit-il rediriger vers `www` ?

## En attente de l'administration (voir `docs/DEMANDES-UX.md` dans `flakeops`)
- Reconstruire le serveur et activer *Internationalization* du royaume `master` (fr, en, es, ar, ko), pour que les messages du thème Keycloak s'affichent. *Chris*
- Vérifier le client OIDC de `www` (identifiant, adresses de retour, scope `profile`) et `KEYCLOAK_REALM_URL`. **Non vérifié.** *Admin / Chris*
- Tester `prompt=create` dans un navigateur. **Non vérifié.** *Chris*
- Compte de service Keycloak pour `just nonreg-onboarding`, puis le lancer ; prouver que le hachage des mots de passe fonctionne. *Chris / Admin*
- Relecture de l'arabe et du coréen (thème Keycloak et site). *Relecteurs natifs*
- Redirection de l'ancien `/signup` (`old.lesgrandsvoisins.com`) vers `/fr/account/inscription/`. *Admin*
- Adresses `@gv.coop` : la zone a un MX mais le domaine n'est pas hébergé, le courrier serait refusé. Nécessaire avant tout alias choisi en `@gv.coop`. *Admin*

## À faire côté UX
- [x] Interface des parcours guidés traduite en en/es/ar/ko.
- [ ] Traduire le CONTENU des parcours (titres, étapes) dans l'administration, en commençant par l'arabe et le coréen (relecteurs natifs).
- [ ] Parcours « documents » (selon la décision 3) et « Vikunja » plus détaillé (nom du projet de relecture à confirmer).
- [x] Test d'inscription dans un navigateur : écrit (`flakeops`, branche `ux/test-inscription-navigateur`, `scripts/nonreg/inscription-navigateur.py`, page `docs/INSCRIPTION-NAVIGATEUR-TEST.md`). **Non vérifié, jamais lancé** ; à fusionner et lancer par l'administration. *Admin / Chris*
- [ ] Doublons d'inscription : message qui oriente vers la connexion sans bloquer (une personne peut avoir un homonyme).
- [ ] Audit d'accessibilité : navigation au clavier, contraste, arabe (droite à gauche), `prefers-reduced-motion`.
- [ ] Courriel de bienvenue (contenu, à envoyer par Keycloak) et écran de bienvenue après la première connexion.
- [ ] Un évènement publié puis modifié reste publié sans nouvelle relecture : décider si la modification le repasse en attente.
- [ ] Création d'un compte nommé proposée en premier par défaut (le numéro anonyme est difficile à garder pour ce public).

## Idées
- Rendre les parcours plus ludiques (défis, petits quiz, « montrer à un voisin »).
- Parcours « aider quelqu'un » pour les personnes qui accompagnent les autres (un voisin qui aide plusieurs personnes).
- Identité collective : associations et entreprises comme fiches d'annuaire plutôt que comptes partagés.
