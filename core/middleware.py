import re

from django.conf import settings


class HoteOutilsMiddleware:
    """
    Sur les noms de domaine de OUTILS_HOSTS (le domaine « côté ordinateur », ex. www.resdigita.com), la page d'accueil de
    chaque langue (/fr/, /en/…) est le tableau de bord des outils (/fr/outils/), sans changer l'adresse affichée.
    Le reste du site (compte, services, connexion) fonctionne à l'identique ; aucun effet si OUTILS_HOSTS est vide.
    """
    ACCUEIL = re.compile(r"^/([a-z]{2})/$")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.OUTILS_HOSTS and request.get_host().split(":")[0] in settings.OUTILS_HOSTS:
            m = self.ACCUEIL.match(request.path_info)
            if m:
                request.path_info = f"/{m.group(1)}/outils/"
        return self.get_response(request)
