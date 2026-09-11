"""Retrouver le compte de la personne qui navigue, qu'il soit anonyme ou nominatif."""
from django.utils.translation import gettext_lazy as _

from .models import Account

SESSION_KEY = "voisinternet_account"
NEW_NUMBER_KEY = "voisinternet_new_number"


def current_account(request, create=False):
    cached = getattr(request, "_voisinternet_account", None)
    if cached is not None:
        return cached

    account = None
    if request.user.is_authenticated:
        account, _created = Account.objects.get_or_create(user=request.user)
    else:
        account_id = request.session.get(SESSION_KEY)
        if account_id:
            account = Account.objects.filter(pk=account_id, user__isnull=True).first()
            if account is None:
                request.session.pop(SESSION_KEY, None)
        if account is None and create:
            account, digits = Account.create_anonymous()
            request.session[SESSION_KEY] = account.pk
            request.session[NEW_NUMBER_KEY] = digits

    if account is not None:
        request._voisinternet_account = account
    return account


def pending_anonymous_account(request):
    """Compte anonyme resté en session alors que la personne s'est connectée."""
    if not request.user.is_authenticated:
        return None
    account_id = request.session.get(SESSION_KEY)
    if not account_id:
        return None
    return Account.objects.filter(pk=account_id, user__isnull=True).first()


def account_label(request):
    """Sous-titre de « je Vois » selon l'état de la personne."""
    if request.user.is_authenticated:
        count = current_account(request).shortcut_set.count()
        return (_("mes raccourcis (%d)") % count if count else _("mon compte")), count
    account = current_account(request)
    if account is None:
        return _("se connecter"), 0
    count = account.shortcut_set.count()
    return (_("mes raccourcis (%d)") % count if count else _("compte anonyme")), count
