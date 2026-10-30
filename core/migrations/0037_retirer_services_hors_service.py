"""Services du catalogue dont l'adresse ne répond plus (constat de Chris le 30/10/2026) : retirés (« proposé » décoché, rien n'est
supprimé : un administrateur peut les remettre) ; le blog pointe désormais vers le blog de ce site."""
from django.db import migrations

HORS_SERVICE = [
    "guichet", "uptime-kuma", "homarr", "keeweb", "crabfit", "quartz", "max-auth", "max-dashy", "ghost", "listmonk",
    "oxicloud", "discourse", "mattermost", "writefreely", "phylum",
]


def retirer(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.filter(slug__in=HORS_SERVICE).update(active=False)
    Service.objects.filter(slug="blog-lesgrandsvoisins-com").update(url="https://www.lesgrandsvoisins.com/fr/blog/")


class Migration(migrations.Migration):
    dependencies = [("core", "0036_mail_redirections")]
    operations = [migrations.RunPython(retirer, migrations.RunPython.noop)]
