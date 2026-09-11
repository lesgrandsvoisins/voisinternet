from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse

from .accounts import account_label, current_account
from .menu import ENTRIES, GROUPS


def _href(entry):
    if entry.target.startswith("setting:"):
        return getattr(settings, entry.target.split(":", 1)[1])
    return reverse(entry.target)


def site(request):
    match = getattr(request, "resolver_match", None)
    current = match.view_name if match else None
    entries = [
        {"entry": e, "href": _href(e), "external": e.target.startswith("setting:"),
         "current": current in {e.target, f"{e.target}_pour"}}
        for e in ENTRIES
    ]
    groups = [
        {"key": key, "caption": caption, "items": [i for i in entries if i["entry"].group == key]}
        for key, caption in GROUPS
    ]
    account = current_account(request)
    account_shortcuts = []
    if account:
        account_shortcuts = account.shortcut_set.select_related("service").order_by("position", "service__order", "service__name")
    label, _ = account_label(request)
    keycloak_login_url = ""
    keycloak_register_url = ""
    if settings.OIDC_ENABLED:
        next_url = request.get_full_path()
        keycloak_login_url = f"{reverse('oidc_authentication_init')}?{urlencode({'next': next_url})}"
        keycloak_register_url = f"{settings.KEYCLOAK_REALM_URL}/protocol/openid-connect/registrations?{urlencode({'client_id': settings.OIDC_RP_CLIENT_ID, 'redirect_uri': request.build_absolute_uri(reverse('core:account'))})}"
    return {
        "conj": {i["entry"].key: i for i in entries},
        "conj_groups": groups,
        "account": account,
        "account_shortcuts": account_shortcuts,
        "account_sub": label,
        "OIDC_ENABLED": settings.OIDC_ENABLED,
        "keycloak_login_url": keycloak_login_url,
        "keycloak_register_url": keycloak_register_url,
        "BLOG_URL": settings.BLOG_URL,
        "GUIDE_URL": settings.GUIDE_URL,
        "CONTACT_EMAIL": settings.CONTACT_EMAIL,
    }
