# Site Wagtail de resdigita.org (« Numérique des Grands Voisins »)

Idée de Chris (31/10) : un site Wagtail distinct pour `resdigita.org`, servi par la même application et le même serveur que `lesgrandsvoisins.com`. Il remplace la décision du 30/10 (soir) de rediriger `resdigita.org` vers `/fr/outils/`. Message : **la sociabilité numérique** — les personnes se retrouvent d'abord dans la vie réelle, l'ordinateur en fait partie. Visuel : variation du dessin de `lesgrandsvoisins.com`, reconnaissable (`core/static/core/img/outils-informatiques.svg`, fourni par Chris).

## État (31/10) : le code est prêt, rien n'est activé
Poussé : type de page `cms.NumeriquePage` (migration cms 0035), accueil servi par nom de domaine (`core.views.home`), thème `theme-numerique` et liens absolus vers le site principal (`core/context_processors.py`, réglage `VOISINTERNET_SITE_PRINCIPAL`), gabarit `cms/templates/cms/numerique_page.html` (visuel, message, tableau de bord dessous), commande `creer_site_resdigita` (simulation par défaut).
À faire sur le serveur : `git pull && deploy/redemarrer.sh`, puis `deploy/manage.sh creer_site_resdigita` (simulation) et `--appliquer`. Le site ne répond qu'une fois les points 4 et 5 ci-dessous faits.

## Ce qu'il faut
1. **Wagtail** : un second `Site` (`www.resdigita.org`) avec sa propre `HomePage` (« Numérique des Grands Voisins »). L'arbre actuel n'est pas touché. Commande de préparation en simulation d'abord.
2. **Identité** : nom et visuel propres au site (`SITE_NAME`, logo, en-tête, pied de page), choisis d'après le nom de domaine ; mêmes styles de base pour rester visiblement apparentés.
3. **Contenu de la page d'accueil** : le visuel, le message (sociabilité numérique), puis le tableau de bord des outils (`/fr/outils/`) en dessous ; pages éditoriales ensuite.
4. **Serveur (administration, DEMANDES-UX)** : remplacer la redirection 302 de `resdigita.org` / `www.resdigita.org` par le service par l'application (module `lgv.voisinternet.outils` déjà préparé) ; `www.resdigita.com` et `www.gv.je` continuent de rediriger vers `https://www.resdigita.org/`.
5. **Réglages** : `www.resdigita.org` dans `DJANGO_ALLOWED_HOSTS` et `DJANGO_CSRF_TRUSTED_ORIGINS` ; adresses de retour de connexion et de déconnexion du client Keycloak `voisinternet`.
6. **À savoir** : connexion et session distinctes d'un nom de domaine à l'autre (le compte Keycloak est le même).

## Synonymes (31/10)
`lesgv.org` et `lesgv.com` sont des synonymes de `resdigita.org` : leurs adresses (apex, `www.` et joker) redirigent en 301 vers `https://www.resdigita.org/` en gardant le chemin. À faire : zones DNS chez ClouDNS (Chris), noms et certificats dans Caddy et redirections (administration). Le courrier de ces noms n'est pas décidé : en attendant, ils sont comptés parmi nos domaines (`VOISINTERNET_DOMAINES_COURRIER`), donc refusés comme cibles de redirection de courrier.
