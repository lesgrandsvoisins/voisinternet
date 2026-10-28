# Journal des mises en ligne de www.lesgrandsvoisins.com

Une ligne par mise en ligne : date, commit, ce qui change, contrôles faits. Recette : [DEPLOIEMENT.md](DEPLOIEMENT.md). Sauvegarde de l'hôte avant chaque mise en ligne : `scripts/sauvegarde-www.sh` (`flakeops`). Aucun secret ici.

| Date | Commit | Ce qui change | Migration | Contrôles | Notes |
|---|---|---|---|---|---|
| 2026-10-28 11:34 | `3197dd1` | Première mise en ligne de ce travail : onboarding (inscription/connexion Keycloak, numéro anonyme conservé, premiers pas, identifiant affiché), parcours guidés, agenda (publication d'un évènement), sélecteur de langue en pied de page, traductions. 20 commits depuis `e8898fe`. | `core.0034` (3 nouvelles tables) | Décomptes identiques ; test de fumée OK sauf le parcours (attendu : fixtures non chargées) | Sauvegarde `2026-10-28-1052`. Parcours chargés ensuite avec `loaddata` (18 objets). |
| 2026-10-28 11:51 | `dcf0019` | Compte anonyme discret (`VOISINTERNET_ANON_ACCOUNTS=discret`), adresses de la boîte lues dans le claim `lgvmail`, test de fumée à jour, anonymisation de la base de qualification. | aucune | Décomptes identiques ; test de fumée complet OK (16 contrôles) | Même sauvegarde. |
| 2026-10-28 12:38 | `1f08e1d` | `robots.txt`, calendrier borné (5 ans en arrière, 3 en avant), `noindex` sur les pages sans intérêt, redirection `/fr/association/` → `/fr/grandsvoisins/`, identifiant et adresses lus aussi dans le jeton d'identité et affichés en haut de « Mon compte ». | aucune | Décomptes identiques ; journal du service sain | Même sauvegarde. |

## État actuel
Production : `1f08e1d` (branche de travail `claude/lesgrandsvoisins-ux-klh29a`, **pas fusionnée dans `main`**). Retour arrière : `git checkout --detach <commit précédent> && systemctl restart voisinter-django`.

## À faire avant la prochaine mise en ligne
- Décider de la fusion dans `main` (aujourd'hui la production suit la branche de travail, ce que la recette autorise pour « essayer »).
- Une sauvegarde plus récente que `2026-10-28-1052` si des données ont beaucoup changé.
