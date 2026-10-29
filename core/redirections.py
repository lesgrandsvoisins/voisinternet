"""
Redirection de courrier choisie par le membre : UNE adresse externe, avec ou sans copie conservée dans sa boîte.

Le membre demande (formulaire) -> un courriel de confirmation part vers l'adresse CIBLE (jeton ≥ 32 octets, usage unique,
24 h, seul le condensé est conservé) -> à la confirmation seulement, l'annuaire est écrit : `mailRoutingAddress` = la cible
(une seule valeur) et `mailLocalAddress` = l'adresse principale (le `cn`) si le membre garde une copie, absent sinon.

Écriture dans l'annuaire par un compte de service limité à ces deux attributs ; son mot de passe est lu dans un fichier,
jamais affiché ni journalisé. L'adresse cible n'est jamais écrite en clair dans les journaux de l'application.
"""
import hashlib
import logging
import secrets
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

logger = logging.getLogger("voisinternet.redirections")

RESERVED_NAMES = {
    "postmaster", "abuse", "noreply", "no-reply", "mailer-daemon", "root", "admin", "administrator", "webmaster",
    "hostmaster", "security", "daemon", "nobody",
}
MAX_REQUESTS_PER_MEMBER = 5
MAX_REQUESTS_PER_TARGET = 3
TOKEN_VALIDITY = timedelta(hours=24)
DAILY_LIMIT = 1000


class RedirectionError(Exception):
    """Erreur affichable à la personne (message déjà traduit, sans secret ni adresse d'un tiers)."""


def digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def mask(address):
    """j***@gmail.com : assez pour se reconnaître, pas pour deviner l'adresse."""
    local, _sep, domain = (address or "").partition("@")
    return f"{local[:1]}***@{domain}" if local else ""


def static_addresses():
    """Adresses dont la redirection est gérée par l'administration (une adresse par ligne, minuscules)."""
    try:
        lignes = Path(settings.REDIRECTIONS_STATIC_FILE).read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    return {l.strip().lower() for l in lignes if l.strip() and not l.lstrip().startswith("#")}


def managed_by_admin(member_addresses):
    statiques = static_addresses()
    return any(a.lower() in statiques for a in member_addresses)


def check_target(target, member_addresses):
    """Adresse normalisée, ou RedirectionError. Refuse : syntaxe invalide, nos domaines, adresses du membre, noms réservés."""
    target = (target or "").strip().lower()
    try:
        validate_email(target)
    except ValidationError:
        raise RedirectionError(_("Cette adresse de courriel n'est pas valide."))
    local, _sep, domain = target.rpartition("@")
    for ours in settings.REDIRECTIONS_OUR_DOMAINS:
        if domain == ours.lower() or domain.endswith("." + ours.lower()):
            raise RedirectionError(_("Choisissez une adresse extérieure à Les Grands Voisins : rediriger vers nos propres domaines n'a pas de sens."))
    if target in {a.lower() for a in member_addresses}:
        raise RedirectionError(_("Cette adresse est l'une des vôtres : la rediriger vers elle-même ferait une boucle."))
    if local.split("+")[0] in RESERVED_NAMES:
        raise RedirectionError(_("Cette adresse est réservée à un usage technique."))
    return target


# --- Annuaire (LDAP) -------------------------------------------------------------------------------------------------

def _connection():
    """Connexion au compte de service. Le mot de passe est lu dans le fichier, jamais ailleurs, jamais journalisé."""
    from ldap3 import Connection, Server

    try:
        secret = Path(settings.LDAP_REDIRECTIONS_SECRET_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        logger.error("redirections: fichier du secret de l'annuaire illisible")
        raise RedirectionError(_("Le service de redirection est momentanément indisponible."))
    return Connection(Server(settings.LDAP_REDIRECTIONS_URI, connect_timeout=5), user=settings.LDAP_REDIRECTIONS_BIND,
                      password=secret, auto_bind=True, receive_timeout=10, raise_exceptions=True)


def find_entry(conn, member_addresses):
    """(dn, cn) de l'UNIQUE entrée dont une valeur de `mail` est une adresse du membre ; sinon refus journalisé."""
    from ldap3.utils.conv import escape_filter_chars

    if not member_addresses:
        raise RedirectionError(_("Votre boîte courriel n'a pas pu être identifiée."))
    filtre = "(|" + "".join(f"(mail={escape_filter_chars(a)})" for a in member_addresses) + ")"
    conn.search(settings.LDAP_REDIRECTIONS_BASE, filtre, attributes=["cn", "mail"])
    entrees = list(conn.entries)
    if len(entrees) != 1:
        logger.warning("redirections: %d entrée(s) trouvée(s) pour une boîte, refus", len(entrees))
        raise RedirectionError(_("Votre boîte courriel n'a pas pu être identifiée."))
    cn = entrees[0].cn.value
    return entrees[0].entry_dn, (cn[0] if isinstance(cn, list) else cn)


def write_directory(member_addresses, target, keep_copy):
    """Écrit (target non vide) ou supprime (target None) la redirection dans l'annuaire."""
    from ldap3 import MODIFY_REPLACE
    from ldap3.core.exceptions import LDAPException

    try:
        conn = _connection()
        try:
            dn, cn = find_entry(conn, member_addresses)
            changes = {
                "mailRoutingAddress": [(MODIFY_REPLACE, [target] if target else [])],
                "mailLocalAddress": [(MODIFY_REPLACE, [cn] if target and keep_copy else [])],
            }
            conn.modify(dn, changes)
        finally:
            conn.unbind()
    except LDAPException as exc:
        # Le texte de l'exception peut citer le DN ou la bind : on n'en journalise que la classe.
        logger.error("redirections: écriture dans l'annuaire refusée (%s)", type(exc).__name__)
        raise RedirectionError(_("Le service de redirection est momentanément indisponible."))


# --- Demandes, confirmation, état ------------------------------------------------------------------------------------

def audit(account, action):
    from .models import RedirectionAudit

    RedirectionAudit.objects.create(account=account, action=action)
    logger.info("redirections: compte=%s action=%s", account.pk, action)


def request_redirection(account, member_addresses, target, keep_copy, confirm_url_for, identifier):
    """Crée la demande et envoie le courriel de confirmation à la cible. `confirm_url_for(token)` donne l'adresse absolue."""
    from .models import RedirectionRequest

    target = check_target(target, member_addresses)
    depuis = timezone.now() - timedelta(days=1)
    if RedirectionRequest.objects.filter(account=account, created__gte=depuis).count() >= MAX_REQUESTS_PER_MEMBER:
        raise RedirectionError(_("Trop de demandes aujourd'hui. Réessayez demain."))
    if RedirectionRequest.objects.filter(target__iexact=target, created__gte=depuis).count() >= MAX_REQUESTS_PER_TARGET:
        raise RedirectionError(_("Cette adresse a reçu trop de demandes aujourd'hui. Réessayez demain."))
    token = secrets.token_urlsafe(32)
    demande = RedirectionRequest.objects.create(
        account=account, target=target, keep_copy=keep_copy, member_addresses=list(member_addresses),
        token_digest=digest(token), expires=timezone.now() + TOKEN_VALIDITY,
    )
    send_mail(
        _("Confirmer la redirection de courrier vers cette adresse"),
        _(
            "Bonjour,\n\n"
            "%(identifier)s, membre de Les Grands Voisins, demande à ce que son courrier soit transféré à cette adresse.\n"
            "Pour accepter, ouvrez ce lien dans les 24 heures :\n\n%(url)s\n\n"
            "Rien ne sera transféré tant que vous n'aurez pas confirmé. Si vous n'êtes pas concerné·e, ignorez ce message : "
            "il expirera tout seul.\n"
        ) % {"identifier": identifier, "url": confirm_url_for(token)},
        settings.DEFAULT_FROM_EMAIL, [target],
    )
    audit(account, "demande")
    return demande


def pending_request(account):
    from .models import RedirectionRequest

    return (RedirectionRequest.objects.filter(account=account, used__isnull=True, expires__gt=timezone.now())
            .order_by("-created").first())


def find_request(token):
    """Demande valable (non utilisée, non expirée) pour ce jeton, ou None."""
    from .models import RedirectionRequest

    demande = RedirectionRequest.objects.filter(token_digest=digest(token or "")).select_related("account__user").first()
    if demande is None or demande.used or demande.expires <= timezone.now():
        return None
    return demande


def confirm(demande):
    """Écrit dans l'annuaire, puis marque la demande utilisée et met à jour l'état affiché."""
    from .models import MailRedirection, RedirectionRequest

    write_directory(demande.member_addresses, demande.target, demande.keep_copy)
    now = timezone.now()
    RedirectionRequest.objects.filter(account=demande.account, used__isnull=True).update(used=now)  # les autres tombent
    MailRedirection.objects.update_or_create(
        account=demande.account,
        defaults={"target": demande.target, "keep_copy": demande.keep_copy, "activated": now},
    )
    audit(demande.account, "activation")


def set_copy(account, member_addresses, keep_copy):
    """Change seulement « garder une copie » (même cible) : pas de nouvelle confirmation."""
    redirection = getattr(account, "mail_redirection", None)
    if redirection is None:
        raise RedirectionError(_("Aucune redirection n'est active."))
    write_directory(member_addresses, redirection.target, keep_copy)
    redirection.keep_copy = keep_copy
    redirection.save(update_fields=["keep_copy"])
    audit(account, "copie_oui" if keep_copy else "copie_non")


def disable(account, member_addresses):
    from .models import MailRedirection, RedirectionRequest

    if hasattr(account, "mail_redirection"):
        write_directory(member_addresses, None, False)
        MailRedirection.objects.filter(account=account).delete()
    RedirectionRequest.objects.filter(account=account, used__isnull=True).update(used=timezone.now())
    audit(account, "desactivation")


def confirm_url(request, token):
    return request.build_absolute_uri(reverse("core:redirection_confirmer", args=[token]))
