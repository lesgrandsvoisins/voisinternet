# Réponses de l'équipe UX à la note de l'administration sur les pages de profil (13/11)

**BROUILLON pour relecture de Chris : rien n'est envoyé à l'administration.** Réponses aux six questions de `docs/NOTE-UX-PROFIL.md` (dépôt `flakeops`, branche `rosest330`). Les textes en arabe et en coréen sont de ma main : à faire relire. Tout ce qui dépend d'une décision de Chris est marqué **[décision]**.

## Principe général
Pas de nouveau formulaire d'identité dans `www` : la personne modifie son profil dans la **console de compte Keycloak** (tout champ modifiable y est écrit dans l'annuaire réel, et `voisinternet` n'écrit jamais dans l'annuaire). Dans `www`, on **montre** l'identifiant, on renvoie vers la console, et on garde la page « Redirection de mes courriels ». Le nom de connexion (`duponlucie` ou `duponlucie@gv.je`) est une décision de Chris **[décision]** ; le texte ci-dessous vaut dans les deux cas.

## 1. Champs obligatoires, et ordre
- **Niveau 1, à l'inscription** (obligatoires) : prénom, nom, **adresse extérieure de référence** (celle qui reçoit le courriel de vérification et sert à retrouver le compte), mot de passe. L'identifiant est **fabriqué**, pas saisi, puis **montré** à la fin de l'inscription.
- **Niveau 2, après l'inscription** (facultatif, dans la console de compte) : un ou plusieurs téléphones, langue, ville, code postal, organisation.
- **Niveau 3, sur demande seulement** : adresse postale, titre, photo, site web.
- **Jamais** : sexe, date de naissance, deuxième prénom, suffixe, civilité. Ni les attributs techniques (`initials`, `shortUsername`, `carLicense`, `lgvmail`, `employeeNumber`).

## 2. Expliquer « identifiant » et « adresse » (trois mots, trois sens)
| | Ce que c'est | Peut-on la changer ? |
|---|---|---|
| **Identifiant** | Votre nom pour vous connecter, le même partout (ex. `duponlucie`). | Non |
| **Adresse Grands Voisins** | Votre boîte de courrier chez nous (ex. `duponlucie@gv.je`). | Non (seule l'administration) |
| **Adresse de référence** | Une adresse que vous avez ailleurs (Gmail, Outlook…) : elle sert à vous joindre et à retrouver votre compte. **Elle ne reçoit pas le courrier de votre boîte.** | Oui, avec confirmation par courriel |

Textes d'aide (à la saisie de l'adresse de référence) :
- **fr** : « Votre adresse personnelle ailleurs (Gmail, Outlook…). Nous nous en servons pour vous joindre et retrouver votre compte. Elle ne reçoit pas le courrier de votre boîte Grands Voisins. »
- **en** : "Your personal address elsewhere (Gmail, Outlook…). We use it to reach you and to help you recover your account. It does not receive the mail of your Grands Voisins mailbox."
- **es** : «Su dirección personal en otro lugar (Gmail, Outlook…). La usamos para contactarle y recuperar su cuenta. No recibe el correo de su buzón de Grands Voisins.»
- **ar** : «عنوانك الشخصي في مكان آخر (Gmail أو Outlook…). نستخدمه للتواصل معك واستعادة حسابك. لا يستقبل بريد صندوقك في Grands Voisins.»
- **ko** : "다른 곳에 있는 개인 주소(Gmail, Outlook 등)입니다. 연락을 드리고 계정을 되찾는 데 사용하며, Grands Voisins 사서함의 메일은 이 주소로 오지 않습니다."

Textes d'aide pour la page « Redirection de mes courriels » (pour ne pas les confondre) :
- **fr** : « Ici, vous faites **suivre** le courrier de votre boîte Grands Voisins vers une autre adresse. Ce n'est pas votre adresse de référence (celle du profil). »
- **en** : "Here you **forward** the mail of your Grands Voisins mailbox to another address. This is not your reference address (the one in your profile)."
- **es** : «Aquí **reenvía** el correo de su buzón de Grands Voisins a otra dirección. No es su dirección de referencia (la del perfil).»
- **ar** : «هنا **تُحوِّل** بريد صندوقك في Grands Voisins إلى عنوان آخر. هذا ليس عنوان المرجع (الموجود في ملفك الشخصي).»
- **ko** : "여기서는 Grands Voisins 사서함의 메일을 다른 주소로 **전달**합니다. 프로필의 참조 주소와는 다릅니다."

## 3. Plusieurs adresses et plusieurs téléphones, sans alourdir
Une seule ligne affichée par défaut ; un lien « Ajouter une adresse » (ou « un téléphone ») ajoute **une** ligne. Pas plus de trois lignes visibles : au-delà, on liste en texte avec un bouton « Modifier ». Sans JavaScript : un champ, un bouton « Ajouter », la page se recharge avec la ligne de plus. La première adresse est « principale » ; chaque ligne a « Retirer ».

## 4. Confirmation par courriel d'une nouvelle adresse de référence
Même patron que « Redirection de mes courriels » (déjà en production) :
1. La personne saisit l'adresse ; elle apparaît tout de suite avec « **En attente de confirmation** par `j***@gmail.com` », un bouton « Renvoyer le courriel » et un bouton « Annuler ».
2. Le courriel part vers cette adresse : lien valable 24 heures, **à usage unique**. Il ouvre une page avec un **bouton « Confirmer »** (un lien de courriel ne confirme jamais à lui seul : les antivirus ouvrent les liens).
3. **L'ancienne adresse reste valable jusqu'à la confirmation.** Tentatives limitées par jour.
4. Rien n'est écrit dans l'annuaire avant la confirmation.

## 5. Quand l'identifiant change
- **Avant** : un courriel d'information aux deux adresses (référence et boîte) quelques jours à l'avance, avec la date et le nouvel identifiant.
- **Le jour même** : à la première connexion, un bandeau **une seule fois** : « Votre identifiant est maintenant `duponlucie`. L'ancien (`…`) ne sert plus. » avec un bouton « J'ai compris ».
- **Une page d'aide** « Mon identifiant a changé » : pourquoi, ce qui change (connexion, courrier, applications), qui contacter.
- **Question à l'administration** : l'ancien identifiant et l'ancienne adresse resteront-ils acceptés un temps (par exemple 90 jours) ? Cela décide du ton du bandeau.
- Dans `voisinternet`, l'identifiant affiché à côté de l'icône du compte vient de Keycloak : il se mettra à jour à la première reconnexion, sans modification du code.

## 6. Vie privée (texte court, à placer sous le formulaire et sur la page d'aide)
- **fr** : « Nous gardons votre nom, votre identifiant, vos adresses et, si vous le donnez, votre téléphone, pour gérer votre compte et votre boîte. Seule l'administration de l'association les voit. Rien n'est vendu ni partagé avec des tiers. Votre fiche de l'annuaire n'est publique que si vous l'avez demandé. Pour consulter, corriger ou effacer vos données : contact@lesgrandsvoisins.com. »
- **en** : "We keep your name, identifier, addresses and, if you give it, your phone number, to manage your account and mailbox. Only the association's administrators can see them. Nothing is sold or shared with third parties. Your directory page is public only if you asked for it. To view, correct or delete your data: contact@lesgrandsvoisins.com."
- **es / ar / ko** : à rédiger après validation du texte français.

## À faire de côté `voisinternet` (rien n'est appliqué)
Page « Redirection de mes courriels » : ajouter le texte d'aide ci-dessus. « Mon compte » : montrer l'identifiant et l'adresse Grands Voisins (non modifiables) avec un bouton « Modifier mon profil » vers la console Keycloak (`{royaume}/account/`). Tests de ces écrans : sur le clone `key.resdigita.org`, quand l'administration le demandera.
