from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse

from .accounts import account_label, current_account
from .menu import ENTRIES, GROUP_PAGES, GROUPS, entry_href

from django.contrib.sites.shortcuts import get_current_site


def site(request):
    match = getattr(request, "resolver_match", None)
    current = match.view_name if match else None
    group_captions = dict(GROUPS)
    entries = [
        {"entry": e, "href": entry_href(e), "external": e.target.startswith("setting:"),
         "current": current in {e.target, f"{e.target}_pour"}, "group_caption": group_captions[e.group]}
        for e in ENTRIES
    ]
    groups = [
        {"key": key, "caption": caption, "items": [i for i in entries if i["entry"].group == key],
         "page_url": reverse(GROUP_PAGES[key]) if key in GROUP_PAGES else None}
        for key, caption in GROUPS
    ]
    # Le menu de l'en-tête n'affiche pas « mon compte » : ce groupe vit dans son propre
    # widget (haut à droite).
    header_groups = [g for g in groups if g["key"] != "compte"]
    account = current_account(request)
    account_shortcuts = []
    if account:
        account_shortcuts = account.shortcut_set.select_related("service").order_by("position", "service__order", "service__name")
    label, _ = account_label(request)
    keycloak_login_url = ""
    keycloak_register_url = ""
    keycloak_account_url = ""
    if settings.OIDC_ENABLED:
        next_url = request.get_full_path()
        keycloak_login_url = f"{reverse('oidc_authentication_init')}?{urlencode({'next': next_url})}"
        keycloak_register_url = f"{settings.KEYCLOAK_REALM_URL}/protocol/openid-connect/registrations?{urlencode({'client_id': settings.OIDC_RP_CLIENT_ID, 'redirect_uri': request.build_absolute_uri(reverse('core:account'))})}"
        keycloak_account_url = f"{settings.KEYCLOAK_REALM_URL}/account/"
    return {
        "conj": {i["entry"].key: i for i in entries},
        "conj_groups": groups,
        "header_groups": header_groups,
        "account": account,
        "account_shortcuts": account_shortcuts,
        "account_sub": label,
        "OIDC_ENABLED": settings.OIDC_ENABLED,
        "keycloak_login_url": keycloak_login_url,
        "keycloak_register_url": keycloak_register_url,
        "keycloak_account_url": keycloak_account_url,
        "BLOG_URL": settings.BLOG_URL,
        "GUIDE_URL": settings.GUIDE_URL,
        "CONTACT_EMAIL": settings.CONTACT_EMAIL,
        "SITE_NAME": get_current_site(request).name,
    }
