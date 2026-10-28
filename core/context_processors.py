from functools import lru_cache
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse
from django.utils.translation import get_language

from .accounts import NEW_NUMBER_KEY, account_label, current_account
from .models import format_number
from .menu import ENTRIES, GROUP_PAGES, GROUPS, entry_href

from django.contrib.sites.shortcuts import get_current_site


@lru_cache(maxsize=256)
def _menu_context(language_code, current):
    # ENTRIES/GROUPS sont des données statiques (core/menu.py) : à langue et page active
    # égales, ce calcul (reverse() compris) donne toujours le même résultat — inutile de
    # le refaire à chaque requête. `language_code` n'est pas utilisé ici directement, mais
    # fait partie de la clé du cache : entry_href()/reverse() dépendent de get_language().
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
    return entries, groups, header_groups


def site(request):
    match = getattr(request, "resolver_match", None)
    current = match.view_name if match else None
    entries, groups, header_groups = _menu_context(get_language(), current)
    account = current_account(request)
    account_shortcuts = []
    if account:
        account_shortcuts = account.shortcut_set.select_related("service").order_by("position", "service__order", "service__name")
    label, _ = account_label(request)
    keycloak_login_url = ""
    keycloak_register_url = ""
    keycloak_account_url = ""
    if settings.OIDC_ENABLED:
        query = urlencode({'next': request.get_full_path()})
        keycloak_login_url = f"{reverse('core:connexion')}?{query}"
        keycloak_register_url = f"{reverse('core:inscription')}?{query}"
        keycloak_account_url = f"{settings.KEYCLOAK_REALM_URL}/account/"
    pending_number = request.session.get(NEW_NUMBER_KEY)
    return {
        "anon_visible": settings.ANONYMOUS_ACCOUNTS == "ouvert",
        "anon_allowed": settings.ANONYMOUS_ACCOUNTS != "ferme",
        "login_identifier": request.session.get("voisinternet_login_identifier", ""),
        "pending_number": format_number(pending_number) if pending_number else None,
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
        "CONTACT_FORMS_ENABLED": settings.CONTACT_FORMS_ENABLED,
        "SITE_NAME": get_current_site(request).name,
    }
