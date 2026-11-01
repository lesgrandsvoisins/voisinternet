# Séparer `www` (données publiques) et `user` (données de la personne) — proposition

Idée de Chris (1/11) : deux applications Django, `www` et `user`, `user` dépendant de `www` : `www` peut contenir des données publiques, alors qu'il faut être prudent avec les données des personnes. **Proposition à valider : rien n'est fait.**

## Règle
`user` peut importer `www` ; `www` n'importe JAMAIS `user` (ni modèle, ni clé étrangère). Ce qui est public et sert à tout le monde est dans `www` ; tout ce qui rattache une donnée à une personne est dans `user`.

## Répartition proposée (modèles actuels de `core`)
| `www` (public) | `user` (personnel) |
|---|---|
| Service, ServiceCategory, Audience, Tag, DirectorySector, GuideBook, Mission, MissionStep, Donor (publics), Event, DirectoryEntry (+ photos) **tels que publiés** | Account, Shortcut, Membership, StepCompletion, EventInterest, EntrySubscription, Contribution, EntryMessage, OwnershipClaim, EventManagementRequest, MailRedirection, RedirectionRequest, RedirectionAudit, Demande, DemandeJournal |
| Pages Wagtail (`cms`, déjà public) | authentification Keycloak, comptes anonymes, session |

## Le point dur : des objets publics qui ont un propriétaire
`DirectoryEntry` et `Event` sont publics mais ont des responsables (`Account`) ; `Contribution`/`EntryMessage` visent une fiche. Pour respecter la règle, le lien « qui gère quoi » passe du côté `user` (table de liaison dans `user`, qui pointe vers l'objet `www`), jamais l'inverse. Les champs privés d'une fiche (courriel de contact, visibilité non publique) restent dans `user` ou sont filtrés à l'écriture.

## Ce que ça apporte réellement
- **Lisibilité et revue** : une relecture de sécurité ne porte que sur `user`.
- **Droits de base de données** : un rôle PostgreSQL en LECTURE SEULE sur les seules tables `www` suffit à servir le site public (aucun accès aux tables `user`). C'est le vrai gain de sécurité ; la séparation des applications seule n'en donne pas.
- **RGPD** : export et effacement d'une personne = tout `user`, sans rien oublier ; sauvegardes et purges par ensemble de tables.
- **Plusieurs sites** (lesgrandsvoisins.com, resdigita.org) : `www` partagé, `user` unique.

## Ce que ça coûte
Étiquette d'application et noms de tables (`core_*`), migrations, noms d'URL (`core:`) dans les gabarits, fixtures (`core.service` → `www.service`), traductions (`modeltranslation`), vue SQL des demandes (`core_demande`, contrat avec l'administration), 213 tests. Réduction du risque : garder `db_table` (aucune table ne change de nom, la vue SQL reste valable), déplacer les modèles par `SeparateDatabaseAndState`, une étape par groupe de modèles, déploiement sans coupure.

## Ordre proposé
1. `user` d'abord (le plus sensible, le plus isolé) : Demande, Redirection*, puis Account et ses dépendances.
2. `www` ensuite : catalogue, agenda, annuaire (avec le lien propriétaire côté `user`).
3. Rôle PostgreSQL en lecture seule pour `www` ; `core` vidé puis supprimé.
Après la bascule de Keycloak (n°18) et l'essai du contrat des demandes (n°17), pour ne pas bouger deux choses à la fois.
