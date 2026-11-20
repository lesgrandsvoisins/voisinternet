# Sites Wagtail par nom de domaine : Max, Hovik, Maher et VIP

Décision de Chris (21/11) : **Max, Hovik et Maher sont des sites individuels** ; **VIP est une racine « bac à sable » pour d'autres sites**. Chaque site existe sous deux noms : `<nom>.resdigita.org` et `<nom>.lesgrandsvoisins.com`.

## Principe
Wagtail choisit le site d'après le nom de domaine (table `Site`). Un nom sans `Site` retombe sur l'accueil de lesgrandsvoisins.com. La commande `creer_site_wagtail` crée, par site : une page d'accueil à la racine de l'arbre, un `Site` par nom de domaine, et (option) un groupe d'**éditeurs limité à ce site** (il modifie et publie seulement les pages sous sa racine, et téléverse images et documents ; on y ajoute les personnes dans `/cms/`, Paramètres, Utilisateurs).

## Commandes (sur le serveur, dans le conteneur ; chacune d'abord SANS `--appliquer`, c'est une simulation)
```sh
deploy/manage.sh creer_site_wagtail Max    max.resdigita.org    max.lesgrandsvoisins.com    --editeurs "Éditeurs de Max"    --appliquer
deploy/manage.sh creer_site_wagtail Hovik  hovik.resdigita.org  hovik.lesgrandsvoisins.com  --editeurs "Éditeurs de Hovik"  --appliquer
deploy/manage.sh creer_site_wagtail Maher  maher.resdigita.org  maher.lesgrandsvoisins.com  --editeurs "Éditeurs de Maher"  --appliquer
deploy/manage.sh creer_site_wagtail VIP    vip.resdigita.org    vip.lesgrandsvoisins.com    --editeurs "Éditeurs de VIP"    --appliquer
```
Avant : les noms doivent être autorisés (`DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`), servis par Caddy et déclarés dans le client Keycloak (adresse de retour `https://<nom>/oidc/callback/`, déconnexion et origines `https://<nom>/*`).

## VIP, bac à sable pour d'autres sites : deux manières
1. **Par chemin (recommandée)** : VIP est un site ; chaque « autre site » est une **page enfant** de sa racine, donc `vip.resdigita.org/fr/<nom>/`. Aucun nom de domaine, aucun certificat, aucune déclaration Keycloak de plus ; les éditeurs de VIP les créent eux-mêmes. Un enfant peut avoir ses propres sous-pages.
2. **Par sous-domaine** (`<nom>.vip.resdigita.org`) : demande un DNS joker, un certificat joker ou à la demande dans Caddy, `DJANGO_ALLOWED_HOSTS` avec `.vip.resdigita.org`, et **chaque sous-domaine déclaré dans Keycloak** (Keycloak n'accepte pas de joker sur le nom d'hôte, seulement en fin de chemin). Lourd ; à n'envisager que si un site doit vraiment avoir son propre nom.

## Décidé le 21/11 (Chris)
- **VIP par chemin** : les autres sites sont des pages enfants de la racine de VIP (`vip.resdigita.org/fr/<nom>/`). La racine de VIP liste ses pages enfants.
- **Sites individuels avec leur propre en-tête** : la page d'accueil d'un site est une `SitePage` (« accueil d'un site » dans Wagtail). Son en-tête affiche le **nom** et la **devise** choisis dans la page (champs « nom dans l'en-tête » et « devise sous le nom » ; à défaut, le titre de la page). Ni le menu, ni l'agenda, ni l'annuaire, ni le logo de lesgrandsvoisins.com ; une icône maison ramène à lesgrandsvoisins.com. Le pied de page porte le nom, la devise et le nom de domaine du site.

- **Un groupe d'éditeurs par site** (créé avec `--editeurs`) ; l'administration y ajoute et en retire les personnes dans `/cms/` (Paramètres, Groupes, ou la fiche d'une personne). Un groupe ne voit que les pages de son site.
- **VIP : page publique, mais le nom est à changer** (en attente d'un nouveau nom).
- **Couleurs par site** : dans la page d'accueil du site (`/cms/`), deux champs facultatifs : « couleur de fond de l'en-tête » et « couleur des boutons », au format `#RRGGBB`. Le site refuse une couleur trop sombre (le texte sombre doit y rester lisible : contraste d'au moins 4,5). Le fond ne s'applique qu'en mode clair (le mode sombre garde ses couleurs) ; la couleur des boutons s'applique dans les deux modes. Les couleurs sont servies par une feuille de style (`/couleurs.css`), sans style en ligne.

## Pas encore décidé
Un nouveau nom pour VIP, si VIP doit être fermé au public, et un logo par site.
