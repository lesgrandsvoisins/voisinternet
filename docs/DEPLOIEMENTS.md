# Journal des mises en ligne de www.lesgrandsvoisins.com

Une ligne par mise en ligne : date, commit, ce qui change, contrôles faits. Recette : [DEPLOIEMENT.md](DEPLOIEMENT.md). Sauvegarde de l'hôte avant chaque mise en ligne : `scripts/sauvegarde-www.sh` (`flakeops`). Aucun secret ici.

| Date | Commit | Ce qui change | Migration | Contrôles | Notes |
|---|---|---|---|---|---|
| 2026-10-28 11:34 | `3197dd1` | Première mise en ligne de ce travail : onboarding (inscription/connexion Keycloak, numéro anonyme conservé, premiers pas, identifiant affiché), parcours guidés, agenda (publication d'un évènement), sélecteur de langue en pied de page, traductions. 20 commits depuis `e8898fe`. | `core.0034` (3 nouvelles tables) | Décomptes identiques ; test de fumée OK sauf le parcours (attendu : fixtures non chargées) | Sauvegarde `2026-10-28-1052`. Parcours chargés ensuite avec `loaddata` (18 objets). |
| 2026-10-28 11:51 | `dcf0019` | Compte anonyme discret (`VOISINTERNET_ANON_ACCOUNTS=discret`), adresses de la boîte lues dans le claim `lgvmail`, test de fumée à jour, anonymisation de la base de qualification. | aucune | Décomptes identiques ; test de fumée complet OK (16 contrôles) | Même sauvegarde. |
| 2026-10-28 12:38 | `1f08e1d` | `robots.txt`, calendrier borné (5 ans en arrière, 3 en avant), `noindex` sur les pages sans intérêt, redirection `/fr/association/` → `/fr/grandsvoisins/`, identifiant et adresses lus aussi dans le jeton d'identité et affichés en haut de « Mon compte ». | aucune | Décomptes identiques ; journal du service sain | Même sauvegarde. |
| 2026-10-28 ~14:05 | `05f2014` (`main`) | Fusion dans `main` (fusion n°1 de Chris + 11 commits) : documentation, `.justfile`, `deploy/manage.sh`, variable `PROJECT`. **Aucun code du site ne change** : pas de redémarrage. | aucune | Essai à blanc conforme (4 commits, dépendances et migrations inchangées) | Première mise à jour faite avec `mise-a-jour.sh main`. |

## État actuel
Production : `05f2014` = `main` (fusionné le 28/10). Le code du site tourne en réalité depuis `1f08e1d` (redémarrage de 12:38), la mise à jour vers `main` n'ayant ajouté que de la documentation et des scripts. Retour arrière : `git checkout --detach <commit précédent> && systemctl restart voisinter-django`.

## À faire avant la prochaine mise en ligne
- La branche `claude/lesgrandsvoisins-ux-klh29a` est abandonnée (tout est dans `main`) : à supprimer sur GitHub (la suppression par push depuis la session de travail est refusée).
- Étiquettes de rattrapage à poser : `v0.1.6` sur `e8898fe` (avant le 28/10), `v0.2.0` sur `1f08e1d` (code en ligne depuis le 28/10 12:38) : voir DEPLOIEMENT.md, « Étiquettes ». Les suivantes : `v0.2.1`, etc.
- Les prochaines mises à jour se font depuis `main` : `deploy/mise-a-jour.sh main` (ou `just maj <dossier>`).
- Une sauvegarde plus récente que `2026-10-28-1052` si des données ont beaucoup changé.
