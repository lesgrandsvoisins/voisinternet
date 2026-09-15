---
title: Numérique autonome et interdépendante
published_at: 2021-09-18T00:00:00.000+02:00
reading_time: 5
excerpt: Nous aimerions aussi dans notre IT mettre en place un principe d’équilibre entre l’autonomie et l’intégration. Nous sommes assez fiers de faire notre propre serveur de courriels. Nous aimons les logiciels libres. De plus, nous adhérons au Contrat pour le Web .
slug: numerique-autonome-et-interdependante
---

Nous aimerions aussi dans notre IT mettre en place un principe d’équilibre entre l’autonomie et l’intégration. Nous sommes assez fiers de faire notre propre serveur de courriels. Nous aimons les logiciels libres. De plus, nous adhérons au [Contrat pour le Web](https://contractfortheweb.org/fr/) . La manière dont nous faisons est déjà ce que nous faisons.

## Pour plus de descriptions

1. La poste électronique de Les Grands Voisins ne sollicite pas d’intermédiaire. L’agent publique de transport de mail (MTA) est notre propre serveur avec les accreditations et certificats requis. La composition et gestion d’abonnements se fait avec le logiciel libre à code source ouverte List Monk sur notre propre serveur.
2. Le lieu de rencontre de vidéoconférence est [https://jitsi.lesgrandsvoisins.com/lesgrandsvoisins](https://jitsi.lesgrandsvoisins.com/lesgrandsvoisins) . Ce dispositif est actuellement ouvert à tous, y compris avec des salles individuelles avec identifiants de vos choix sans limite dans le temps ou le nombre de personnes au-dela de la capacité du serveur. Nous administrons pleinement ce dispositif.
3. Ce site [mailing.lesgrandsvoisins.com](http://mailing.lesgrandsvoisins.com) est entièrement administré avec un logiciel libre Discourse sur nos serveurs. Cela deviendra [https://discourse.lesgrandsvoisins.com](https://discourse.lesgrandsvoisins.com), car il s’agit de cette technologie libre à source ouverte.
4. Notre site statique [https://www.lesgrandsvoisins.com](https://www.lesgrandsvoisins.com) est aussi administré sur nos serveurs. Nous projetons de migrer pour le site plaquette de migrer vers [https://apostrophe.lesgrandsvoisins.com](https://apostrophe.lesgrandsvoisins.com) sur la technologie [ApostropheCMS](https://www.apostrophecms.com) libre et à source ouverte.

# Scoop ! Grève de la Poste électronique

Depuis une semaine (du 20 au 26 août), notre serveur de relai publique autonome de courriels n’envoyait plus de courriels pour ni pour [notre site Discourse](https://mailing.lesgrandsvoisins.com/) ni pour le site ListMonk. Cela vaut dire que toute personne s’étant inscrite pendant ce temps soit conformer son abonnement pour recevoir des gazettes futures. Exceptionnellement, j’inclus la dernière gazette pour information, mais **pensez bien à confirmer vos abonnements svp** (lien, puis buton après lien dans la page au but du lien). Merci de vos compréhensions. La poste électronique des Grands Voisins a mis fin à son grève ce jour, vendredi 27 août 2021.

# Remplacer Google Apps

Voici comment je souhaiterais remplacer Google Apps et Office 365.

Chaque utilisateur dispose d’un compte Posix.

Chaque compte Posix dispose d’un MailPile, d’un compte Dovecot, Postfix, WebDav.

SeaFile s’occupe du partage de fichiers.

Le WebDav can centralize iCal etc.

## MEET: [jitsi.lesgrandsvoisins.com](http://jitsi.lesgrandsvoisins.com/) (Jisti Meet Vidéoconférences)

Ceci remplace Zoom ou Google Meet. Change to [meet.lesgrandsvoisins.com](http://meet.lesgrandsvoisins.com/).

## DISC: [mailing.lesgrandsvoisins.com](http://mailing.lesgrandsvoisins.com/) (Discourse pour faire communauté)

Ceci est un serveur d’articles peu structurées accessibles en web et en mobile. Il se présente comme web app sur les mobiles à partir d’un premier accès web. Il pourra être aussi notre centre d’authentification et d’authorisation d’utilisateurs.

Tous doux: renommer [mailing.lesgrandsvoisins.com](http://mailing.lesgrandsvoisins.com/) en [disc.lesgrandsvoisins.com](http://disc.lesgrandsvoisins.com/).

### EMAIL: [email.lesgrandsvoisins.com](http://email.lesgrandsvoisins.com/) (SOGo Calendrier, Contacts et Tâches)

Ceci est un webmail avec de calendriers, de carnets d’addresses et de listes de tâches. C’est compatible avec tous les clients PC et mobiles sans accès web. L’administration se fait à travers [email.lesgrandsvoisins.com/iredadmin](http://email.lesgrandsvoisins.com/iredadmin).

## WWW: [www.lesgrandsvoisins.com/login](http://www.lesgrandsvoisins.com/login) (ApostropeCMS pour la gestion de contenu)

Nous utilisons ApostropeCMS, OpenSource professionnel extraordinaire pour la gestion du contenu de la présentation du portail de Les Grands Voisins. C’est un peu les fonctions que nous aurions eu de WordPress, de SquareSpace ou de Wix pour éditer et designer sans coder.

## SMTP: [mail.lesgrandsvoisins.com:587](http://mail.lesgrandsvoisins.com:587/) (Postfix &amp; Dovecot pour la poste numérique, ou l’autonomie de courriels)

Nous avons configuré notre serveur SMTP depuis notre propre serveur public avec les certificats, configurations et enregistrements nécessaires pour délivrer directement les courriels aux boîtes des destinataires. Cela nous permet de maîtriser l’information pour le compte de nos membres et nos amis.

Tous doux: scinder les trois serveurs actuellement tous les trois [mail.lesgrandsvoisins.com](http://mail.lesgrandsvoisins.com/) en [mail.lesgrandsvoisins.com](http://mail.lesgrandsvoisins.com/), [smtp.lesgrandsvoisins.com](http://smtp.lesgrandsvoisins.com/) et [imap.lesgrandsvoisins.com](http://imap.lesgrandsvoisins.com/) (éventuellement [pop3.lesgrandsvoisins.com](http://pop3.lesgrandsvoisins.com/) aussi). Il y a aussi plein de petites choses à ajouter: Sieve, antivirus, spam assasin, …

## Beta

### FILE: [file.lesgrandsvoisins.com](http://file.lesgrandsvoisins.com/) (Seafile Cloud Drive)

Ceci remplace iCloud, Miscrosoft OneDrive our Google Drive.

Toux doux:

- Forward http to https

## Alpha

### MAIL: [cyp.lesgrandsvoisins.com](http://cyp.lesgrandsvoisins.com/) (Serveur IMAP pour consulter courriels de [lesgrandsvoisins.com](http://lesgrandsvoisins.com/))

Ceci remplace Gmail. C’est un serveur en réception de courriels. C’est compatible avec tous les clients web, PC et mobiles.

Toux doux: pointer MX [lesgrandsvoisins.com](http://lesgrandsvoisins.com/) SMTP pour stockage sur [imap.lesgrandsvoisins.com](http://imap.lesgrandsvoisins.com/).

### FOR: [forem.lesgrandsvoisins.com](http://forem.lesgrandsvoisins.com/) (Forem pour le média social propriétaire des Grands Voisins) (ambition)

Il s’agit de mettre à disposition un site Forem qui remplace les fonctions de Facebook.

### SO: [gneighbor.com/SOGo](http://gneighbor.com/SOGo/) (SOGo Webmail, Calendrier, Contacts et Tâches) (ambition)

J’apprécie beaucoup SOGo et souhaiterais en faire un serveur pour notre workflow. C’est la croix et la baniêre ou 750 euros à installer.

## Conception

### CMS: … (ApostropheCMS Assembly pour la gestion de contenu de multiples sites de multiples voisins) (ambition)

J’aimerais mettre en place l’ensemble ApostropheCMS Assemblee pour proposer aux voisins un alternatif à Wordpress pour le côté plaquette, SquareSpace ou Wix.

## Rejeté

### [cube.lesgrandsvoisins.com](http://cube.lesgrandsvoisins.com/) (RoundCube Webmail)

Ceci est un interface basic pour accéder aux courriels IMAP. Il ne marche que par PC il me semble.

### CAL: [cale.lesgrandsvoisins.com](http://cale.lesgrandsvoisins.com/) (Radicale Calendrier, Contacts et Tâches)

Ceci est un serveur webdav de calendriers, de carnets d’addresses et de listes de tâches. C’est compatible avec tous les clients PC et mobiles sans accès web. Change to [cal.lesgrandsvoisins.com](http://cal.lesgrandsvoisins.com/).

La poste numérique des Grands Voisins est maintenant doté d’un dispositif [email.lesgrandsvoisins.com](http://email.lesgrandsvoisins.com/). Ce dispositif permet un accès web performant en logiciel libre à son courriel, son calendrier (avec tâches) et à son carnet d’adresses. C’est comparable à Gmail, calendar et drive, sauf en libre sous Les Grands Voisins.

## [Nouveau Dispositif Web pour la Poste Electronique des Grands Voisins](https://mailing.lesgrandsvoisins.com/t/numerique-autonome-et-interdependante/41)

La poste numérique des Grands Voisins est maintenant doté d’un dispositif [laposte.lesgrandsvoisins.com](https://laposte.lesgrandsvoisins.com/). Ce dispositif permet un accès web performant en logiciel libre à son courriel, son calendrier (avec tâches) et à son carnet d’adresses. C’est comparable à Gmail, calendar et drive, sauf en libre sous Les Grands Voisins.

EXTRA: Ceux qui utilisaient [email.lesgrandsvoisins.com](http://email.lesgrandsvoisins.com/) vont prochainement migrer vers [laposte.lesgrandsvoisins.com](http://laposte.lesgrandsvoisins.com/). Red Hat vient de faire don de six mois du service en logiciel libre [easy.iRedMail.org](https://www.iredmail.org/easy.html) aux Grands Voisins. Merci Red Hat !

Pour rappel, toute personne peut utiliser notre serveur de viséo-conference: [jitsi.lesgrandsvoisins.com](https://jitsi.lesgrandsvoisins.com/)

# Nouveau dispositif de statistiques

Nous venons de mettre en place des statistiques [plausible.io](http://plausible.io/) à l’instant pour [mailing.lesgrandsvoisins.com](http://mailing.lesgrandsvoisins.com/) et [www.lesgradsvoisins.com](http://www.lesgradsvoisins.com/).

## Dispositifs

Liste des dispositifs Les Grands Voisins:

[https://www.lesgrandsvoisins.com/fr/](https://www.lesgrandsvoisins.com/fr/)

A la base de [apostrophecms.com](http://apostrophecms.com)

[https://mail.lesgv.com/SOGo/index/](https://mail.lesgv.com/SOGo/index/)

A la base de [iredmail.org](http://iredmail.org), sogo.nu, Postfix, Dovecot, OpenLDAP

[https://list.lesgrandsvoisins.com](https://list.lesgrandsvoisins.com)

A la base de [listmonk.org](http://listmonk.org)

[https://jitsi.lesgrandsvoisins.com](https://jitsi.lesgrandsvoisins.com)

A la base de [jitsi.org](http://jitsi.org) (?). Viseoconference comme Zoom ou Google Meet.

[https://file.lesgrandsvoisins.com](https://file.lesgrandsvoisins.com)

A la base de [seafile.org](http://seafile.org) (ou seafile) pour remplace dropbox. future [collabora.org](http://collabora.org) pour remplacer Google sheets, docs et slides.

[https://mailing.lesgrandsvoisins.com](https://mailing.lesgrandsvoisins.com)

A la base de [discourse.org](http://discourse.org) pour faire forum de discussion

[https://forem.lesgrnadsvoisins.com](https://forem.lesgrnadsvoisins.com)

A la base de [forem.com](http://forem.com) (ou [forem.org](http://forem.org)) pour remplacer Facebook.