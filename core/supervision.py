"""
État des outils (vert / jaune / rouge) lu dans la supervision EXISTANTE de l'hôte : Prometheus + blackbox_exporter (job « sites »), requête
`probe_success{job="sites"}`. Décision de Chris (20/11) : pas de seconde série de sondes ; le site lit et met en cache.

Règles :
  - AU PLUS UNE requête par minute vers Prometheus, même si cent personnes ouvrent la page : cache partagé (fichier, entre les processus) et
    verrou d'une minute ; les autres visiteurs reçoivent la dernière valeur connue ;
  - délai court (2 s) ; en cas d'échec, la dernière valeur connue est gardée (marquée ancienne), jamais une erreur de page ;
  - l'étiquette `instance` de la sonde est le NOM DU SITE sans schéma : on la rapproche du nom d'hôte de l'adresse du service du catalogue ;
  - seule la requête /api/v1/query avec probe_success est appelée ; l'adresse de base est réglable (VOISINTERNET_SUPERVISION_URL ; vide = désactivé).

États : vert (répond), rouge (ne répond pas), jaune (mesure de plus de 2 minutes, ou lenteur), gris « inconnu » (pas de mesure, ou supervision
injoignable depuis plus de 10 minutes).
"""
import json
import logging
import time
from urllib.error import URLError
from urllib.parse import quote, urlparse
from urllib.request import urlopen

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger("voisinternet.supervision")

CLE = "supervision:probe_success"
CLE_VERROU = "supervision:verrou"
INTERVALLE = 60          # secondes entre deux requêtes vers Prometheus (au plus une par minute, tous visiteurs confondus)
DELAI = 2                # délai de la requête sortante, en secondes
MESURE_ANCIENNE = 120    # une mesure plus vieille est « jaune » (la sonde tourne toutes les 30 s)
SUPERVISION_PERDUE = 600  # sans nouvelle de Prometheus depuis 10 minutes : « inconnu »

ETATS = {
    "vert": ("●", _("En ligne")),
    "jaune": ("▲", _("À vérifier")),
    "rouge": ("■", _("Hors ligne")),
    "inconnu": ("○", _("Inconnu")),
}


def _lire():
    """{instance: (valeur_texte, horodatage_epoch)} d'après Prometheus ; lève une exception en cas d'échec."""
    base = settings.SUPERVISION_URL.rstrip("/")
    requete = quote('probe_success{job="sites"}', safe="")
    with urlopen(f"{base}/api/v1/query?query={requete}", timeout=DELAI) as reponse:
        donnees = json.loads(reponse.read().decode("utf-8"))
    if donnees.get("status") != "success":
        raise ValueError("réponse de supervision inattendue")
    sondes = {}
    for resultat in donnees["data"]["result"]:
        instance = resultat["metric"].get("instance") or resultat["metric"].get("site")
        horodatage, valeur = resultat["value"]
        if instance:
            sondes[instance.lower()] = (str(valeur), float(horodatage))
    return sondes


def _donnees(maintenant):
    """Dernière lecture connue ({"recu": epoch, "sondes": {...}}), rafraîchie au plus une fois par minute."""
    donnees = cache.get(CLE)
    if donnees is None or maintenant - donnees["recu"] >= INTERVALLE:
        if cache.add(CLE_VERROU, 1, INTERVALLE):   # un seul rafraîchissement par minute, même en cas d'échec
            try:
                donnees = {"recu": maintenant, "sondes": _lire()}
                cache.set(CLE, donnees, 3600)
            except (URLError, OSError, ValueError, KeyError, TypeError) as exc:
                logger.warning("supervision injoignable ou illisible (%s) : dernière valeur gardée", type(exc).__name__)
    return donnees


def etat_de(sonde, recu, maintenant):
    """Code d'état (vert, jaune, rouge, inconnu) d'une mesure (valeur_texte, horodatage) reçue à l'instant `recu`."""
    if sonde is None or recu is None or maintenant - recu > SUPERVISION_PERDUE:
        return "inconnu"
    valeur, horodatage = sonde
    if valeur == "0":
        return "rouge"
    if valeur != "1" or maintenant - horodatage > MESURE_ANCIENNE or maintenant - recu > MESURE_ANCIENNE:
        return "jaune"
    return "vert"


def annoter(services):
    """Pose `service.etat` ({"code", "symbole", "libelle"}) sur chaque service ; renvoie l'état global (code) ou "" si la supervision est désactivée."""
    if not settings.SUPERVISION_URL:
        return ""
    maintenant = time.time()
    donnees = _donnees(maintenant)
    sondes = donnees["sondes"] if donnees else {}
    recu = donnees["recu"] if donnees else None
    codes = []
    for service in services:
        hote = (urlparse(service.url).hostname or "").lower() if service.url else ""
        sonde = sondes.get(hote) if hote else None
        if sonde is None and hote:
            continue   # service non sondé par la supervision : pas de pastille
        if not hote:
            continue
        code = etat_de(sonde, recu, maintenant)
        symbole, libelle = ETATS[code]
        service.etat = {"code": code, "symbole": symbole, "libelle": libelle}
        codes.append(code)
    if not codes:
        return "inconnu" if donnees is None else ""
    for pire in ("rouge", "jaune", "inconnu"):
        if pire in codes:
            return pire
    return "vert"


GLOBAL = {
    "vert": _("Tout fonctionne"),
    "jaune": _("Un service est lent ou son état est à vérifier"),
    "rouge": _("Un service ne répond pas"),
    "inconnu": _("État des services inconnu"),
}
