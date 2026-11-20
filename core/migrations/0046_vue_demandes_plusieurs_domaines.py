"""
Vue v_demandes_a_appliquer (PostgreSQL seulement) : accepte aussi les adresses de RÉCEPTION en @lesgrandsvoisins.com (décision de Chris, 21/11).
Défense en profondeur inchangée : forme de la partie locale, et domaines par type : « adresse » (réception) = resdigita.org ou
lesgrandsvoisins.com ; « envoi » = resdigita.org seulement. La fonction demande_marquer n'est pas touchée. Sur SQLite : sans effet.
"""
from django.db import migrations

CREER = r"""
CREATE OR REPLACE VIEW v_demandes_a_appliquer AS
SELECT id, kind AS type, demandeur, local_part || '@' || domain AS adresse, decided AS approuvee_le
FROM core_demande
WHERE state = 'approuvee'
  AND (
        (kind = 'adresse' AND (local_part || '@' || domain) ~ '^[a-z0-9][a-z0-9._-]{0,63}@(resdigita\.org|lesgrandsvoisins\.com)$')
     OR (kind = 'envoi'   AND (local_part || '@' || domain) ~ '^[a-z0-9][a-z0-9._-]{0,63}@resdigita\.org$')
  );
"""

ANCIENNE = r"""
CREATE OR REPLACE VIEW v_demandes_a_appliquer AS
SELECT id, kind AS type, demandeur, local_part || '@' || domain AS adresse, decided AS approuvee_le
FROM core_demande
WHERE state = 'approuvee'
  AND (local_part || '@' || domain) ~ '^[a-z0-9][a-z0-9._-]{0,63}@resdigita\.org$';
"""


def creer(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(CREER)


def annuler(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(ANCIENNE)


class Migration(migrations.Migration):
    dependencies = [("core", "0045_service_supervision_instance")]
    operations = [migrations.RunPython(creer, annuler)]
