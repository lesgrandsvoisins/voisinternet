---
title: Naissance de la Gazette hedbo
published_at: 2021-07-24T00:00:00.000+02:00
reading_time: 3
excerpt: Le 29 juillet 2021, nous avons envoyé notre premier newsletter de LesGrandsVoisins.com. Dans cette gazette de LesgrandsVoisins.com 1, nous avons promu les principes directeurs du manifeste et avons suivi notre informatique engagée. On y trouve particulièrement les nouvelles sur LesGrandsVoisins.com et les choses à venir. Vous pouvez vous y inscrire ici.

Le site mailing.LesGrandsVoisins.com est une implémentation du logiciel « Discourse.org » avec pour objectif de composer et rendre disponible l
slug: naissance-de-la-gazette-hedbo
featured_image: ./images/2023/04/lemonde-2017.original-1.png
---

Le 29 juillet 2021, nous avons envoyé notre premier newsletter de [LesGrandsVoisins.com](http://lesgrandsvoisins.com/). Dans cette gazette de [LesgrandsVoisins.com 1](http://lesgrandsvoisins.com/), nous avons promu les principes directeurs du manifeste et avons suivi notre informatique engagée. On y trouve particulièrement les nouvelles sur [LesGrandsVoisins.com](http://lesgrandsvoisins.com/) et les choses à venir. [**Vous pouvez vous y inscrire ici**](https://list.lesgrandsvoisins.com/subscription/form).

Le site [mailing.LesGrandsVoisins.com](http://mailing.lesgrandsvoisins.com/) est une implémentation du logiciel « [Discourse.org](http://discourse.org/) » avec pour objectif de composer et rendre disponible les infos de [LesGrandsVoisins.com](http://lesgrandsvoisins.com/). Nous pouvons être plusieurs à y contribuer et cela sert aussi à avoir des communications entre nous, éditeurs et auteurs.

Le site [list.LesGrandsVoisins.com](http://list.lesgrandsvoisins.com/) est une implémentation du logiciel « ListMonk.app » avec pour objectif de diffuser la gazette hebdomadaire à tous ceux qui souhaitent en recevoir. Ce dispositif, de même l’ensemble des dispositifs, repose sur un serveur de courriel (dit MTA ou Mail Transfer Agent) autonome de livraison de courriel.

[LesGrandsVoisins.com](http://lesgrandsvoisins.com/) suivent le [contractfortheweb.org](http://contractfortheweb.org/).

Ceci est un dispositif « Discourse » que j’ai configuré dans un format « mailing list. » Cette configuration de « mailing list » est une intention: je souhaite que le dispositif « Discourse » prenne la place d’un newsletter.

Pour l’instant, je pense que la configuration permet uniquement la diffusion des messages depuis le site Discourse [mailing.LesGrandsVoisins.com](http://mailing.lesgrandsvoisins.com/) vers les abonnés. #todo rechercher comment configurer la boite de reception des messages pour alimenter Discourse, éventuellement.

Est-ce que ce fonctionnement convient à la communauté ?

Par ailleurs, je veins de prendre connaissance d’une [charte de la communauté](https://forum.lesgrandsvoisins.com/guidelines) standard à Discourse avec des conseils pratiques.

Après usage, il me semble que Discourse envoy un courriel à chaque nouveau « topic » publié. Cela fait que chaque Topic devient un newsletter. Est-ce que nous voulons ?

Par ailleurs, la configuration « correcte » d’une boîte de reception par Discourse fera que lorsque les personnes répondent aux mels du site, ces mels peuvent s’insérer directement dans le site pour la considération de tout le monde. Cela peut faire aussi en sorte que tout courriel répondu puisse, si c’est configuré ainsi, être encore redistribué à tous.

Je viens de désactiver « Mailing List Mode ». Avant, chacun recevait un message à chaque création de nouveau sujet. Maintenant, ce n’est plus le cas.

Je pense que quand je vais produire un mailing list, je ne suis pas certain de comment procéder. je suppose que je peux activer « mailing list mode » uniquement quand j’écris un « topic » de newsletter, puis désactiver la fonction par ailleurs. La configuration de catégories telle que la catégorie « Newsletter » soit la seule visible peut en effet produire le même résultat.

Par ailleurs, il est nécessaire d’inscrire les personnes avec uniquement un courriel, un nom de famille et un prénom. L’obligation du mot de passe est trop complexe. Pour arriver à ce résultat, je me demande si je peux coder un processus d’inscription.

Parallèlement à la question d’inscription, la mise en place de social logins peut faciliter la chose.

Je viens d’activer les logins sociaux : Facebook, Twitter, Google, Github, Discord.

Two links with interesting information and points on the subject.

- [https://meta.discourse.org/t/apply-mailing-list-mode-per-category/47772/8](https://meta.discourse.org/t/apply-mailing-list-mode-per-category/47772/8)
- [What is "Mailing List mode"? - support - Discourse Meta](https://meta.discourse.org/t/what-is-mailing-list-mode/46008)
- [Setting defaults to enable mailing list mode-Temporary Solution - support - Discourse Meta](https://meta.discourse.org/t/setting-defaults-to-enable-mailing-list-mode-temporary-solution/25645)

But, I guess List Monk would perhaps be better:

- [https://listmonk.app/](https://listmonk.app/)

Le site était hors ligne de 6h à 7h40 de matin ce vendredi 30 juillet, 2021. J’ai mis en place un serveur proxy Apache afin de pouvoir intégrer d’autres applications sur ce même serveur. Je prévois l’installation de [ListMonk](https://listmonk.app/) prochainement.

Listmonk fonctionne tr\`es bien sur [list.lesgrandsvoisins.fr](https://list.lesgrandsvoisins.com/subscription/form). J’en suis ravi. NB quand vous vous y inscrivez, il faut aussi appuyer sur le bouton dans la page de validation. La démarche me semble respectueuse, nottament du [contractfortheweb.com](http://contractfortheweb.com/).