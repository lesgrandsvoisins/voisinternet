# Anonymisation d'une copie de la base (pour la qualification)

> **Liste des données personnelles de `www` pour l'administration**, et script SQL généré à partir des vrais modèles. **Testé sur SQLite seulement**, avec de fausses données personnelles (fiche privée, utilisateur, messages, session, évènement, donateur) : les 11 contrôles valent 0 et la base reste intègre. **Non testé sur PostgreSQL** (syntaxe volontairement simple : `UPDATE`, `DELETE`, `||`, `CAST`). Ne jamais restaurer le vrai dump de production dans la qualification sans passer par ce script.

## Mode d'emploi
1. Restaurer la sauvegarde dans une base **séparée** (autre nom, autre rôle), jamais dans la base de production.
2. Remplacer `QUALIF_NOM_DE_DOMAINE` dans `deploy/anonymisation.sql` par le nom de la qualification.
3. Exécuter **dans une seule transaction, en s'arrêtant à la première erreur** (par exemple `psql -v ON_ERROR_STOP=1 -1 -d <base de qualification> -f deploy/anonymisation.sql`). Vérifier d'abord que `\c` pointe bien la base de qualification.
4. Les requêtes de contrôle en fin de fichier **doivent toutes renvoyer 0**. Sinon, ne pas démarrer l'application.
5. Hors du fichier : **ne pas copier `media/`** (photos de personnes) ; `EMAIL_HOST` vide ; `DJANGO_SECRET_KEY` et `VOISINTERNET_ANON_PEPPER` **différents** de ceux de production ; démarrer l'application.
Le fichier est généré : `.venv/bin/python manage.py shell < tools/generer_anonymisation.py` (à refaire si un champ est ajouté).

## Ce qui est anonymisé (table → colonnes → traitement)
| Table | Colonnes | Traitement |
|---|---|---|
| `django_session` | tout | **supprimé** (contient des numéros de compte anonyme en clair, des identifiants de compte) |
| `django_admin_log`, `wagtailcore_modellogentry`, `wagtailcore_pagelogentry` | tout | supprimé (noms d'utilisateurs, libellés) |
| `wagtailcore_comment`, `wagtailcore_commentreply` | tout | supprimé (texte libre) |
| `wagtailforms_formsubmission` | tout | supprimé (réponses de formulaires) |
| `core_entrymessage`, `cms_authormessage` | tout | supprimé (nom, courriel et texte de l'expéditeur) |
| `auth_user` | `username`, `email`, `first_name`, `last_name`, `password`, `last_login` | remplacés par `test-<id>`, `test-<id>@exemple.invalid`, « Test », « Utilisateur <id> », mot de passe **inutilisable** (la connexion passe par le Keycloak de qualification), date vide |
| `core_account` | `number_digest` | **NULL** (empreinte du numéro anonyme : dépend du secret de production) |
| `core_directoryentry` | `email`, `phone`, `address`, `postal_code`, `website`, `video_url`, `cta_link` | vidés pour **toutes** les fiches |
| `core_directoryentry` (fiches **non publiques ou non validées**) | `name`, `title`, `tagline`, `description`, `cta_intro`, `cta_label`, `city`, `region`, `logo`, `photo_promo` (+ langues `_fr/_en/_es/_ar/_ko`), `slug` | vidés ; nom « Fiche test <id> », slug `fiche-test-<id>` (le slug est tiré du nom de la personne) |
| `core_directoryentryphoto` | lignes des fiches non publiques ; `caption` | supprimées ; légendes vidées |
| `core_contribution` | `note` (+ langues) | vidé (montants, mode, date conservés : sans le compte, ils n'identifient personne) |
| `core_donor` | `name` (+ langues) | « Donateur <id> » |
| `core_event` | `online_url` (tous) ; `title`, `slug`, `description`, `location` (évènements **non publiés**) | lien de visioconférence vidé ; évènements non publiés remplacés (« Évènement test <id> ») |
| `cms_author` | `email` | vidé |
| `wagtailcore_site`, `django_site` (si présent) | `hostname`, `domain` | nom de la qualification (sinon les liens absolus pointent vers la production) |

## Ce qui est volontairement conservé, et pourquoi
- **Contenus éditoriaux publics** : pages Wagtail, évènements publiés, services, publics, parcours guidés, **fiches d'annuaire publiques et validées** (déjà visibles de tous sur `www`, avec le consentement de leurs auteurs ; seules leurs coordonnées sont retirées). Si vous préférez ne jamais copier ces fiches non plus, ajoutez-les à la règle « non publiques ».
- **Structure et identifiants numériques** (clés étrangères, droits, groupes) : indispensables au fonctionnement.
- **Ensembles de comptes et leurs liens** (raccourcis, groupes, intérêts) : sans empreinte de numéro ni identité, ce sont des données de test.

## Ce que ce script ne couvre PAS (à traiter à part)
- Le dossier **`media/`** : ne pas le copier (photos de personnes, logos). Les images manqueront dans la qualification, ce qui est attendu.
- **`wagtailcore_revision`** : l'historique des pages contient leur contenu, brouillons compris. Pas de données de membres a priori, mais des textes non publiés : à garder ou à supprimer selon l'usage voulu.
- **Textes libres des fiches publiques** et des pages : relus par leurs auteurs avant publication, mais pas par ce script.
- **Keycloak et l'annuaire LDAP** : hors de `www` ; la qualification utilise un royaume Keycloak distinct, sans fédération LDAP (condition posée par l'administration).
- **Journaux du serveur** (`voisinter-django-access.log`, 215 Mo au 25/10) : contiennent des adresses IP ; ne pas les copier.
