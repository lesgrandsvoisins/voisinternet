"""
Demandes soumises à la modération : le membre demande (adresse de réception, droit d'envoyer depuis une adresse), un
modérateur (groupe « Modération ») approuve ou refuse, l'administration applique. voisinternet n'écrit JAMAIS dans l'annuaire :
il enregistre et fait approuver (voir la vue SQL v_demandes_a_appliquer, migration 0041).

La sécurité tient à trois règles : liste fermée de domaines, partie locale restreinte, noms réservés refusés.
"""
import logging
import re
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .redirections import RESERVED_NAMES

logger = logging.getLogger("voisinternet.demandes")

GROUPE = "Modération"
LOCAL_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
RESERVES = RESERVED_NAMES | {
    "contact", "info", "bienvenue", "list", "listes", "support", "help", "aide", "billing", "compta", "tresorerie",
    "president", "presidence", "bureau", "ca", "direction", "www", "mail", "ftp", "smtp", "imap", "pop", "dkim", "dmarc",
    "keycloak", "ghost", "wiki", "blog", "key", "ldap", "dns", "ssl", "tls", "abuse-report",
}
NOTIFICATION_DELAI = 3600  # au plus un courriel groupé par heure aux modérateurs


class DemandeError(Exception):
    """Erreur affichable à la personne (message déjà traduit, sans secret)."""


def domaines():
    return list(settings.DEMANDES_DOMAINES)


def moderateurs():
    return get_user_model().objects.filter(groups__name=GROUPE, is_active=True).distinct()


def est_moderateur(user):
    return user.is_authenticated and user.groups.filter(name=GROUPE).exists()


def identifiant_local(demandeur):
    """Partie locale de l'identifiant du membre (preferred_username sans « @gv.je »)."""
    return (demandeur or "").split("@")[0].strip().lower()


def valider(kind, local_part, domain):
    """(partie locale normalisée, domaine) ou DemandeError."""
    from .models import Demande, Service

    local_part = (local_part or "").strip().lower()
    domain = (domain or "").strip().lower()
    if kind not in (Demande.ADRESSE, Demande.ENVOI):
        raise DemandeError(_("Type de demande inconnu."))
    if domain not in domaines():
        raise DemandeError(_("Ce domaine n'est pas proposé."))
    if not LOCAL_RE.match(local_part):
        raise DemandeError(_("La partie avant « @ » doit commencer par une lettre minuscule ou un chiffre, puis ne contenir que des lettres minuscules, chiffres, points, tirets ou tirets bas (64 caractères au plus)."))
    if local_part.split("+")[0] in RESERVES or Service.objects.filter(slug=local_part).exists():
        raise DemandeError(_("Cette adresse est réservée."))
    return local_part, domain


def _verifier_envoi(kind, demandeur, local_part, domain):
    """L'envoi n'est possible que depuis l'adresse du membre (son identifiant) ou une adresse de réception déjà accordée."""
    from .models import Demande

    propre = identifiant_local(demandeur)
    if kind == Demande.ENVOI and local_part != propre and not Demande.objects.filter(
        demandeur=demandeur, kind=Demande.ADRESSE, state=Demande.APPLIQUEE, local_part=local_part, domain=domain,
    ).exists():
        raise DemandeError(_("Envoi possible depuis l'adresse propre à la personne (%(adresse)s) ou depuis une adresse de réception déjà accordée.") % {"adresse": f"{propre}@{domain}"})


IDENTIFIANT_RE = re.compile(r"^[a-z0-9][a-z0-9._@-]{0,148}$")


def autoriser(moderateur, demandeur, kind, local_part, domain, reason=""):
    """Autorisation donnée DIRECTEMENT par la modération (déjà « approuvée »), sans demande préalable de la personne. Même
    validation et même contrat que les demandes : l'administration applique, voisinternet n'écrit jamais dans l'annuaire."""
    from .models import Account, Demande, DemandeJournal

    demandeur = (demandeur or "").strip().lower()
    if not IDENTIFIANT_RE.match(demandeur):
        raise DemandeError(_("Identifiant invalide : indiquez l'identifiant de la personne (par exemple prenom.nom@gv.je)."))
    local_part = (local_part or "").strip().lower() or identifiant_local(demandeur)
    local_part, domain = valider(kind, local_part, domain)
    if kind == Demande.ADRESSE and local_part == identifiant_local(demandeur):
        raise DemandeError(_("Cette adresse est déjà celle de la personne."))
    _verifier_envoi(kind, demandeur, local_part, domain)
    account = Account.objects.filter(user__username=demandeur).first()
    try:
        with transaction.atomic():
            demande = Demande.objects.create(
                kind=kind, account=account, demandeur=demandeur, local_part=local_part, domain=domain,
                reason=(reason or "").strip()[:1000], state=Demande.APPROUVEE, moderator=str(moderateur),
                decided=timezone.now(),
            )
    except IntegrityError:
        raise DemandeError(_("Cette adresse fait déjà l'objet d'une demande."))
    DemandeJournal.objects.create(demande=demande, acteur=str(moderateur), action="autorisee")
    logger.info("demandes: %s autorisée directement (%s)", demande.pk, demande.kind)
    return demande


def creer(account, demandeur, kind, local_part, domain, reason):
    """Crée la demande (en attente), sinon DemandeError. Une seule demande en attente par membre et par adresse."""
    from .models import Demande, DemandeJournal

    local_part, domain = valider(kind, local_part, domain)
    propre = identifiant_local(demandeur)
    if kind == Demande.ADRESSE and local_part == propre:
        raise DemandeError(_("Cette adresse est déjà la vôtre."))
    _verifier_envoi(kind, demandeur, local_part, domain)
    depuis = timezone.now() - timedelta(days=1)
    if Demande.objects.filter(account=account, created__gte=depuis).count() >= settings.DEMANDES_PAR_JOUR:
        raise DemandeError(_("Trop de demandes aujourd'hui. Réessayez demain."))
    if Demande.objects.filter(account=account, state=Demande.ATTENTE).exists():
        raise DemandeError(_("Vous avez déjà une demande en attente : attendez la décision avant d'en faire une autre."))
    try:
        with transaction.atomic():
            demande = Demande.objects.create(
                kind=kind, account=account, demandeur=demandeur, local_part=local_part, domain=domain,
                reason=(reason or "").strip()[:1000],
            )
    except IntegrityError:
        raise DemandeError(_("Cette adresse fait déjà l'objet d'une demande."))
    DemandeJournal.objects.create(demande=demande, acteur=demandeur, action="demande")
    logger.info("demandes: %s demande %s", demande.pk, demande.kind)
    _prevenir_moderation(demande)
    return demande


def decider(demande, moderateur, approuver, commentaire=""):
    """Approuve ou refuse une demande en attente (une seule décision)."""
    from .models import Demande, DemandeJournal

    with transaction.atomic():
        demande = Demande.objects.select_for_update().get(pk=demande.pk)
        if demande.state != Demande.ATTENTE:
            raise DemandeError(_("Cette demande a déjà été traitée."))
        demande.state = Demande.APPROUVEE if approuver else Demande.REFUSEE
        demande.moderator = str(moderateur)
        demande.moderator_comment = (commentaire or "").strip()[:1000]
        demande.decided = timezone.now()
        demande.save(update_fields=["state", "moderator", "moderator_comment", "decided"])
        DemandeJournal.objects.create(demande=demande, acteur=str(moderateur), action="approuvee" if approuver else "refusee")
    _prevenir_demandeur(demande)
    return demande


def _courriel_demandeur(demande):
    user = demande.account.user if demande.account else None
    return user.email if user and user.email else ""


def _prevenir_demandeur(demande):
    """Courriel de décision, sans secret."""
    cible = _courriel_demandeur(demande)
    if not cible:
        return
    if demande.state == demande.APPROUVEE:
        corps = _("Votre demande pour %(adresse)s a été approuvée. L'administration l'applique dans les minutes qui suivent ; l'état s'affiche dans « Mes demandes».") % {"adresse": demande.address}
    else:
        corps = _("Votre demande pour %(adresse)s a été refusée.") % {"adresse": demande.address}
    if demande.moderator_comment:
        corps += "\n\n" + _("Commentaire de la modération :") + "\n" + demande.moderator_comment
    send_mail(_("Votre demande d'adresse"), corps, settings.DEFAULT_FROM_EMAIL, [cible], fail_silently=True)


def _prevenir_moderation(demande):
    """Un seul courriel groupé par heure aux modérateurs."""
    if not cache.add("demandes:notification", 1, NOTIFICATION_DELAI):
        return
    destinataires = [u.email for u in moderateurs() if u.email]
    if not destinataires:
        return
    send_mail(
        _("Nouvelle demande à modérer"),
        _("Une ou plusieurs demandes attendent la modération. Ouvrez la page « Modération » du site pour les traiter.\n"),
        settings.DEFAULT_FROM_EMAIL, destinataires, fail_silently=True,
    )
