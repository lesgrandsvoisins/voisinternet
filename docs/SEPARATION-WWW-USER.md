# Séparer `www`, `portal` et `user` — proposition

Idée de Chris (1/11) : séparer les applications Django : `www` peut contenir des données publiques, alors qu'il faut être prudent avec les données des personnes (`user`, qui dépend de `www`). Précision du même jour : **l'annuaire et l'agenda deviennent une application à part, `portal`.** **Proposition à valider : rien n'est fait.**

## Règle
Sens des dépendances : `user` → `portal` → `www`. Une application n'importe JAMAIS une application plus haut dans cette chaîne (`www` ne connaît ni `portal` ni `user` ; `portal` ne connaît pas `user`) : ni modèle, ni clé étrangère. Ce qui est public et sert à tout le monde est dans `www` ; l'annuaire et l'agenda (publics, mais vivants et gérés par des personnes) dans `portal` ; tout ce qui rattache une donnée à une personne est dans `user`.

## Répartition proposée (modèles actuels de `core`)
| `www` (public, stable) | `portal` (annuaire et agenda) | `user` (personnel) |
|---|---|---|
| Service, ServiceCategory, Audience, Tag, GuideBook, Mission, MissionStep, Donor (publics) ; pages Wagtail (`cms`, déjà public) | DirectoryEntry (+ photos), DirectorySector, Event, avec leurs pages et leur recherche | Account, Shortcut, Membership, StepCompletion, EventInterest, EntrySubscription, Contribution, EntryMessage, OwnershipClaim, EventManagementRequest, MailRedirection, RedirectionRequest, RedirectionAudit, Demande, DemandeJournal ; authentification Keycloak, comptes anonymes, session |

## Le point dur : des objets publics qui ont un propriétaire
`DirectoryEntry` et `Event` (désormais dans `portal`) sont publics mais ont des responsables (`Account`) ; `Contribution`/`EntryMessage` visent une fiche. Pour respecter la règle, le lien « qui gère quoi » passe du côté `user` (table de liaison dans `user`, qui pointe vers l'objet `portal`), jamais l'inverse. Autres liens à couper : les fiches et évènements qui renvoient à `Audience`/`Tag` (dans `www`, sens permis) ; le catalogue qui n'a pas à connaître l'annuaire. Les champs privés d'une fiche (courriel de contact, visibilité non publique) restent dans `user` ou sont filtrés à l'écriture.

## Ce que ça apporte réellement
- **Lisibilité et revue** : une relecture de sécurité ne porte que sur `user`.
- **Droits de base de données** : un rôle PostgreSQL en LECTURE SEULE sur les seules tables `www` suffit à servir le site public (aucun accès aux tables `user`). C'est le vrai gain de sécurité ; la séparation des applications seule n'en donne pas.
- **RGPD** : export et effacement d'une personne = tout `user`, sans rien oublier ; sauvegardes et purges par ensemble de tables.
- **Plusieurs sites** (lesgrandsvoisins.com, resdigita.org) : `www` partagé, `user` unique.

## Ce que ça coûte
Étiquette d'application et noms de tables (`core_*`), migrations, noms d'URL (`core:`) dans les gabarits, fixtures (`core.service` → `www.service`), traductions (`modeltranslation`), vue SQL des demandes (`core_demande`, contrat avec l'administration), 213 tests. Réduction du risque : garder `db_table` (aucune table ne change de nom, la vue SQL reste valable), déplacer les modèles par `SeparateDatabaseAndState`, une étape par groupe de modèles, déploiement sans coupure.

## Ordre proposé
1. `user` d'abord (le plus sensible, le plus isolé) : Demande, Redirection*, puis Account et ses dépendances.
2. `portal` ensuite : annuaire et agenda (avec le lien propriétaire côté `user`).
3. `www` : catalogue, publics, étiquettes, parcours.
4. Rôle PostgreSQL en lecture seule pour `www` et `portal` (tables publiées) ; `core` vidé puis supprimé.
Après la bascule de Keycloak (n°18) et l'essai du contrat des demandes (n°17), pour ne pas bouger deux choses à la fois.
