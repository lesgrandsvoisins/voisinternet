from django.conf import settings
from django.urls import reverse

from .accounts import account_label
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
         "current": e.target == current}
        for e in ENTRIES
    ]
    groups = [
        {"key": key, "caption": caption, "items": [i for i in entries if i["entry"].group == key]}
        for key, caption in GROUPS
    ]
    label, count = account_label(request)
    return {
        "conj": {i["entry"].key: i for i in entries},
        "conj_groups": groups,
        "account_sub": label,
        "account_count": count,
        "OIDC_ENABLED": settings.OIDC_ENABLED,
        "BLOG_URL": settings.BLOG_URL,
        "GUIDE_URL": settings.GUIDE_URL,
        "CONTACT_EMAIL": settings.CONTACT_EMAIL,
    }
