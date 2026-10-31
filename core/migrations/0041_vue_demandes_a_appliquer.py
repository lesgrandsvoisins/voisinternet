"""
Contrat avec l'administration (PostgreSQL seulement) : l'application ne touche jamais à l'annuaire ; l'administration lit les
demandes approuvées par la vue v_demandes_a_appliquer et renvoie le résultat par la fonction demande_marquer, via le rôle
lgv_demandes (SELECT sur la vue + EXECUTE sur la fonction, rien d'autre : le rôle et les GRANT sont créés par
l'administration, pas ici).

  - la vue ne montre que les demandes « approuvée » dont l'adresse respecte déjà ^[a-z0-9][a-z0-9._-]{0,63}@resdigita.org$
    (défense en profondeur, en plus de la validation de l'application) ;
  - demande_marquer(id, resultat, message) ne fait passer QU'approuvée -> appliquée/échec (jamais l'inverse) ; message ≤ 200 car.
Sur SQLite (tests, développement) cette migration ne fait rien.
"""
from django.db import migrations

CREER = r"""
CREATE OR REPLACE VIEW v_demandes_a_appliquer AS
SELECT id, kind AS type, demandeur, local_part || '@' || domain AS adresse, decided AS approuvee_le
FROM core_demande
WHERE state = 'approuvee'
  AND (local_part || '@' || domain) ~ '^[a-z0-9][a-z0-9._-]{0,63}@resdigita\.org$';

CREATE OR REPLACE FUNCTION demande_marquer(p_id bigint, p_resultat text, p_message text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  nouvel_etat text;
  n integer;
BEGIN
  IF p_resultat = 'appliquee' THEN nouvel_etat := 'appliquee';
  ELSIF p_resultat = 'echec' THEN nouvel_etat := 'echec';
  ELSE RAISE EXCEPTION 'resultat inconnu';
  END IF;
  UPDATE core_demande
     SET state = nouvel_etat, result_message = left(coalesce(p_message, ''), 200), applied = now()
   WHERE id = p_id AND state = 'approuvee';
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n = 1;
END;
$$;

REVOKE ALL ON FUNCTION demande_marquer(bigint, text, text) FROM PUBLIC;
"""

SUPPRIMER = """
DROP FUNCTION IF EXISTS demande_marquer(bigint, text, text);
DROP VIEW IF EXISTS v_demandes_a_appliquer;
"""


def creer(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(CREER)


def supprimer(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SUPPRIMER)


class Migration(migrations.Migration):
    dependencies = [("core", "0040_groupe_moderation")]
    operations = [migrations.RunPython(creer, supprimer)]
