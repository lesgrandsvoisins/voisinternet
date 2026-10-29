# Backlog

Ce qui reste à faire pour `www.lesgrandsvoisins.com`. Identifiants `U-nnn` (le backlog d'administration de `chris2fr/flakeops`, branche `rosest330`, utilise `B-nnn` : les deux peuvent finir dans un même projet Vikunja sans collision). États : `a_faire`, `en_cours`, `bloque`, `fait`. Responsables : **Chris**, **Admin** (session d'administration des serveurs), **UX** (cette session). Ce qui est fait est daté dans [CHANGELOG.md](CHANGELOG.md). Tout ce qui n'est pas vérifié sur le vrai serveur est marqué **non vérifié**. Aucun secret ici.

Les besoins côté serveur passent par `docs/DEMANDES-UX.md` (dépôt `flakeops`) ; l'administration les suit sous `B-0nn`.

## P0 — Décisions de Chris
| ID | État | Tâche | Resp. | Terminé quand |
|---|---|---|---|---|
| U-001 | en_cours | **Identifiant** : décidé le 27/10 (relayé par l'Admin) : jusqu'à 5 lettres du nom + 5 du prénom, numéro seulement si pris. Code : `flakeops` `ux/identifiant-sans-compteur` (`6b9d846`) ; textes : `ux/identifiant-textes` (`1e82518`). **Non fusionnés, non déployés.** Reste la question de l'adresse choisie (`B-036`, bloquée). | Admin / Chris | Fusionné avec les textes, reconstruit, essayé en vrai. |
| U-002 | a_faire | **Logo du pied de page** : il affiche « new.LesGrandsVoisins.com » (`partials/wordmark.html`). « www. » ou sans préfixe ? | Chris | Choix noté ; UX modifie le gabarit. |
| U-003 | a_faire | **« Mark for documents »** : préciser (relecture ? marquage ? Markdown ?) pour en faire un parcours guidé. | Chris | Description reçue. |
| U-006 | a_faire | **Second courriel** : les nouveaux membres pourraient aussi recevoir `nom@lesgrandsvoisins.com` en deuxième valeur `mail` (comme l'ancien compte `lesgv2`). Question relayée par l'Admin, rien de préparé. | Chris | Décision notée. |
| U-004 | a_faire | **Blog** : `blog.lesgrandsvoisins.com` doit-il rediriger vers `www` ? (`B-035` côté admin) | Chris | Décision notée. |
| U-005 | a_faire | **Accès à Vikunja** pour la relecture ar/ko : qui peut l'obtenir ? Le parcours dit « demandez-nous un accès ». | Chris | Règle d'accès notée ; le parcours est ajusté. |

## P1 — Pour que l'inscription fonctionne de bout en bout (côté serveur)
| ID | État | Tâche | Resp. | Terminé quand |
|---|---|---|---|---|
| U-010 | bloque | Reconstruire et activer *Internationalization* du royaume `master` (fr, en, es, ar, ko) ; `B-004`. | Chris | L'écran d'inscription s'affiche en français avec `ui_locales=fr`. |
| U-011 | bloque | Tester `prompt=create` dans un navigateur ; `B-005`. **Non vérifié.** | Chris | Le bouton « Créer mon compte » de `www` ouvre directement le formulaire d'inscription. |
| U-012 | bloque | Vérifier le client OIDC de `www` (identifiant, adresses de retour, scope `profile`) et `KEYCLOAK_REALM_URL` ; `B-033`. **Non vérifié.** | Chris / Admin | Une connexion depuis `www` montre l'identifiant dans « Mon profil ». |
| U-013 | bloque | Compte de service Keycloak, puis lancer `just nonreg-onboarding` ; prouver que le hachage des mots de passe fonctionne ; `B-002`. | Chris / Admin | Test vert. |
| U-014 | a_faire | Premier lancement du test d'inscription navigateur (`scripts/nonreg/inscription-navigateur.py`, fusionné ; `B-020`). Prérequis : Playwright + Chromium, compte de service, chemin du fichier secret. **Non vérifié, jamais lancé.** | Chris | Test passé une fois ; corriger les KO de forme. |
| U-015 | a_faire | Avant ce premier lancement : vérifier que l'adresse de la machine est dans `ignoreip` de fail2ban (une connexion de test échouée alimente la jaille `keycloak`). **Non vérifié.** | Chris | Vérifié. |
| U-016 | a_faire | Si l'appel du jeton échoue au premier lancement : `KC_URL` vaut `https://key.gv.je` dans le test, alors que `onboarding.py` utilise le port local avec les en-têtes `X-Forwarded`. | UX / Admin | Le test obtient un jeton. |
| U-017 | bloque | Redirection de l'ancien `/signup` (`old.lesgrandsvoisins.com`) vers `/fr/account/inscription/` ; `B-034`. Attend `U-011` et `U-013`. | Admin | `curl -I` renvoie 301. |
| U-018 | bloque | Héberger `@gv.coop` (zone avec MX, domaine absent de `modules/mail/domains.nix`, courrier refusé ; `B-006`). Prérequis de tout alias en `@gv.coop`. | Admin / Chris | Un envoi de test à `@gv.coop` arrive. |
| U-019 | a_faire | **`B-039` (P0)** : l'entrée d'annuaire créée par une inscription n'a AUCUNE valeur `mail` (`bobbob2`, `duvoloui`) : un nouveau membre se connecte au SSO mais n'a pas de boîte. Ne rien promettre sur la boîte tant que ce n'est pas résolu. Le parcours « Ma boîte courriel » est masqué en attendant. | Admin | Cause trouvée (le courriel Keycloak va dans `uid`, `mail` vient de l'attribut `lgvmail` que l'inscription ne remplit pas) ; correctif prêt sur `flakeops` `ux/identifiant-sans-compteur` (`090d374`), non déployé ; une inscription test a une adresse ; parcours courriel réactivé (administration > parcours guidés). |
| U-028 | a_faire | **Noms en alphabet non latin** (arabe, coréen) : le générateur ne garde que a–z, un tel nom donne « aucun identifiant disponible » sans issue (`B-038`). Le thème demande des lettres latines et propose d'écrire à contact@ ; il faudrait une vraie solution (translittération, identifiant proposé par l'équipe). **À signaler/décider.** | Chris / Admin | Un membre arabophone ou coréanophone peut s'inscrire seul. |

| U-029 | a_faire | **Purger les comptes anonymes** (1 973 comptes dont 1 956 anonymes au 28/10, presque tous vides) : à faire plus tard (décision de Chris). Prudence : supprimer un compte supprime ses raccourcis, groupes, intérêts et dons ; ne purger que les comptes **sans aucune donnée liée** et anciens. Commande à écrire (essai à blanc par défaut). | UX / Chris | Comptes vides supprimés, décomptes avant/après notés. |
| U-030 | a_faire | **Environnement de qualification** : proposition dans `docs/QUALIFICATION.md` ; la partie serveur est à évaluer par l'Admin. | Chris / Admin | Décision ; si oui, demande dans `DEMANDES-UX.md`. |

| U-031 | a_faire | Inscription Keycloak (demande Admin du 28/10, `B-043`) : (1) champ identifiant en lecture seule « calculé pour vous » : thème 0.2.0 écrit (`flakeops` `ux/inscription-lecture-seule`, `a8280db`), **non déployé, non essayé dans Keycloak** ; (2) textes du royaume proposés dans `docs/TEXTES-ROYAUME.md`, à appliquer par Chris ; (3) adresses lues dans le claim `lgvmail` (demande n°9 : protocol mapper) ; (4) test navigateur adapté (5+5 sans numéro, deux `mail`) ; (5) le lien d'inscription de `www` part de `client_id=<OIDC_RP_CLIENT_ID>` (voisinternet), pas de la console d'administration : voir réponse à l'Admin. | UX / Admin / Chris | Une inscription test sur la qualification ou la production : identifiant lu en lecture seule, deux adresses affichées, arrivée sur `www`. |

| U-033 | en_cours | **Import écrit (`import_ancien_association`), à lancer en production puis relire/publier** ; reprise de la section Association de l'ancien site (36 pages : Conseils n°21 à 27 avec votes, statuts, équipe, mission, historique, devenir membre…) en brouillon, d'après `contenu.jsonl`. Décidé le 29/10 : l'équipe est reprise, les textes Ghost sont bons. Reste : IBAN de la page « Dons » de Ghost (public, à confirmer), index « Conseils des voisins ». | Claude | Pages en brouillon relues, liens `old` remplacés. |
| U-032 | a_faire | Journal de production du 28/10 : beaucoup de trafic de robots (ClaudeBot, DotBot, bingbot, scanners `cache.php`, `wp-admin`), `/fr/association/` en 404 depuis Bing (ancienne adresse), journal d'accès de 215 Mo. `robots.txt`, calendrier borné et première redirection (`/fr/association/` → `/fr/grandsvoisins/`, table `LEGACY_REDIRECTS`) faits ; **fait pour `/fr-fr/…` (vue `ancien_site`, d'après l'export de `old`) ; à vérifier en production après mise à jour : les 24 fiches d'annuaire et 11 évènements de l'ancien site sans équivalent public tombent sur la rubrique** ; reste à décider : limitation de débit côté Caddy, rotation du journal, redirection des anciennes adresses (`B-0xx` ?). | Admin / UX / Chris | Trafic de robots maîtrisé ; anciennes adresses redirigées. |

## P2 — À faire côté UX
| ID | État | Tâche | Resp. | Terminé quand |
|---|---|---|---|---|
| U-020 | a_faire | Traduire le **contenu** des parcours guidés (titres, étapes) en ar et ko d'abord, via l'administration. Relecteurs natifs. | UX / relecteurs | Parcours lisibles en ar et ko. |
| U-021 | a_faire | Relecture de l'arabe et du coréen du thème Keycloak et de l'interface du site. | Relecteurs natifs | Relecture notée. |
| U-022 | a_faire | Parcours « documents » (selon `U-003`) et parcours Vikunja plus précis (nom du projet de relecture à confirmer). | UX | Parcours publiés. |
| U-023 | a_faire | Doublons d'inscription : message qui oriente vers la connexion sans bloquer (homonymes possibles). Côté thème Keycloak, les messages existent ; reste le cas « même nom » sur `www`. | UX | Message en place. |
| U-024 | a_faire | Audit d'accessibilité : navigation au clavier, contraste restant, arabe (droite à gauche), `prefers-reduced-motion`. | UX | Anomalies corrigées. |
| U-025 | a_faire | Courriel de bienvenue (contenu, à envoyer par Keycloak) et écran de bienvenue après la première connexion. | UX / Admin | Contenu écrit ; envoi configuré. |
| U-026 | a_faire | Un évènement publié puis modifié reste publié sans relecture : décider si la modification le repasse en attente. | UX / Chris | Décision appliquée. |
| U-027 | a_faire | Proposer en premier la création d'un compte nommé (le numéro anonyme est difficile à garder pour ce public). | UX | Ordre et textes changés. |
| U-030 | a_faire | Traduire en en/es/ar/ko les nouveaux libellés des raccourcis (`make messages`, puis relecture). | Claude + relecteurs | `.po` à jour, libellés relus |

## P3 — Idées
- Rendre les parcours plus ludiques (défis, petits quiz, « montrer à un voisin »).
- Parcours « aider quelqu'un » pour les personnes qui accompagnent les autres.
- Identité collective : associations et entreprises comme fiches d'annuaire plutôt que comptes partagés.
- Adresse choisie en alias : l'administration penche pour un petit service côté serveur appelé par `www` (conception `B-036`, rien sans accord de Chris). `www` n'aura jamais d'accès à l'annuaire LDAP.

## Fait
- Test d'inscription dans un navigateur écrit et fusionné (`flakeops`, `scripts/nonreg/inscription-navigateur.py`).
- Parcours guidés (interface traduite en en/es/ar/ko), bandeau du numéro anonyme, boutons inscription/connexion, identifiant affiché : voir [CHANGELOG.md](CHANGELOG.md).
