-- Anonymisation d'une COPIE de la base de www.lesgrandsvoisins.com (voisinter-django). GÉNÉRÉ par tools/generer_anonymisation.py : ne pas éditer à la main.
-- NE JAMAIS l'exécuter sur la base de production. À lancer UNIQUEMENT sur une base de qualification restaurée depuis une sauvegarde,
-- dans une transaction, puis vérifier avec les requêtes de contrôle en fin de fichier (elles doivent toutes renvoyer 0).
-- Pas de secrets ici. Écrit pour PostgreSQL ; syntaxe volontairement simple (UPDATE/DELETE, || et CAST) pour rester portable.
-- Reste à faire HORS de ce fichier : ne pas copier le dossier media/ (photos de personnes) ; EMAIL_HOST vide ; SECRET_KEY et
-- VOISINTERNET_ANON_PEPPER distincts ; remplacer QUALIF_NOM_DE_DOMAINE ci-dessous par le nom de la qualification.
BEGIN;

-- 1. Données de session et journaux : vidés (les sessions contiennent des numéros de compte anonyme en clair).
DELETE FROM django_session;
DELETE FROM django_admin_log;
DELETE FROM wagtailcore_modellogentry;
DELETE FROM wagtailcore_pagelogentry;
DELETE FROM wagtailcore_commentreply;
DELETE FROM wagtailcore_comment;
DELETE FROM wagtailforms_formsubmission;

-- 2. Messages reçus par le site (formulaires de contact) : vidés.
DELETE FROM core_entrymessage;
DELETE FROM cms_authormessage;

-- 3. Utilisateurs : identité remplacée, mot de passe local inutilisable (la connexion se fait par Keycloak de qualification).
UPDATE auth_user SET username = 'test-' || CAST(id AS TEXT), first_name = 'Test', last_name = 'Utilisateur ' || CAST(id AS TEXT), email = 'test-' || CAST(id AS TEXT) || '@exemple.invalid', password = '!anonymise', last_login = NULL;

-- 4. Comptes : l'empreinte du numéro anonyme est supprimée (elle dépend du secret de production).
UPDATE core_account SET number_digest = NULL;

-- 5. Annuaire : coordonnées retirées pour TOUTES les fiches ; fiches non publiques ou non validées : texte libre vidé aussi.
UPDATE core_directoryentry SET email = '', phone = '', address = '', postal_code = '', website = '', video_url = '', cta_link = '';
UPDATE core_directoryentry SET name = '', name_fr = NULL, name_en = NULL, name_es = NULL, name_ar = NULL, name_ko = NULL, title = '', title_fr = NULL, title_en = NULL, title_es = NULL, title_ar = NULL, title_ko = NULL, tagline = '', tagline_fr = NULL, tagline_en = NULL, tagline_es = NULL, tagline_ar = NULL, tagline_ko = NULL, description = '', description_fr = NULL, description_en = NULL, description_es = NULL, description_ar = NULL, description_ko = NULL, cta_intro = '', cta_intro_fr = NULL, cta_intro_en = NULL, cta_intro_es = NULL, cta_intro_ar = NULL, cta_intro_ko = NULL, cta_label = '', cta_label_fr = NULL, cta_label_en = NULL, cta_label_es = NULL, cta_label_ar = NULL, cta_label_ko = NULL, city = '', region = '', logo = '', photo_promo = '' WHERE NOT (visibility = 'public' AND approved);
-- Le slug d'une fiche est tiré du nom de la personne : remplacé lui aussi.
UPDATE core_directoryentry SET name = 'Fiche test ' || CAST(id AS TEXT), name_fr = 'Fiche test ' || CAST(id AS TEXT), slug = 'fiche-test-' || CAST(id AS TEXT) WHERE NOT (visibility = 'public' AND approved);
DELETE FROM core_directoryentryphoto WHERE entry_id IN (SELECT id FROM core_directoryentry WHERE NOT (visibility = 'public' AND approved));
UPDATE core_directoryentryphoto SET caption = '';

-- 6. Dons : notes libres vidées ; noms de donateurs remplacés.
UPDATE core_contribution SET note = '', note_fr = NULL, note_en = NULL, note_es = NULL, note_ar = NULL, note_ko = NULL;
UPDATE core_donor SET name = '', name_fr = NULL, name_en = NULL, name_es = NULL, name_ar = NULL, name_ko = NULL;
UPDATE core_donor SET name = 'Donateur ' || CAST(id AS TEXT), name_fr = 'Donateur ' || CAST(id AS TEXT);

-- 7. Agenda : lien de visioconférence retiré partout ; textes des évènements non publiés vidés.
UPDATE core_event SET online_url = '';
UPDATE core_event SET description = '', description_fr = NULL, description_en = NULL, description_es = NULL, description_ar = NULL, description_ko = NULL, location = '', location_fr = NULL, location_en = NULL, location_es = NULL, location_ar = NULL, location_ko = NULL WHERE NOT public;
UPDATE core_event SET title = 'Évènement test ' || CAST(id AS TEXT), title_fr = 'Évènement test ' || CAST(id AS TEXT), slug = 'evenement-test-' || CAST(id AS TEXT) WHERE NOT public;

-- 8. Auteurs du blog : courriel retiré.
UPDATE cms_author SET email = '';

-- 9. Adresses du site : à remplacer par le nom de la qualification (sinon les liens absolus pointent vers la production).
UPDATE wagtailcore_site SET hostname = 'QUALIF_NOM_DE_DOMAINE', port = 443, is_default_site = TRUE;

-- Contrôles : chaque requête doit renvoyer 0 après anonymisation.
SELECT COUNT(*) FROM auth_user WHERE email NOT LIKE '%@exemple.invalid' OR password <> '!anonymise';
SELECT COUNT(*) FROM core_account WHERE number_digest IS NOT NULL;
SELECT COUNT(*) FROM core_directoryentry WHERE email <> '' OR phone <> '' OR address <> '';
SELECT COUNT(*) FROM django_session;
SELECT COUNT(*) FROM core_entrymessage;
SELECT COUNT(*) FROM cms_authormessage;
SELECT COUNT(*) FROM core_event WHERE online_url <> '';
SELECT COUNT(*) FROM core_donor WHERE name NOT LIKE 'Donateur %';
SELECT COUNT(*) FROM core_directoryentry WHERE NOT (visibility = 'public' AND approved) AND (slug NOT LIKE 'fiche-test-%' OR name NOT LIKE 'Fiche test %');
SELECT COUNT(*) FROM core_event WHERE NOT public AND slug NOT LIKE 'evenement-test-%';
SELECT COUNT(*) FROM wagtailcore_site WHERE hostname <> 'QUALIF_NOM_DE_DOMAINE';

COMMIT;
