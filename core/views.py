from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .accounts import NEW_NUMBER_KEY, SESSION_KEY, current_account, pending_anonymous_account
from .ghost import latest_posts
from .models import Account, Donor, GuideBook, Service, Shortcut, format_number


def _is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def _shortcut_ids(request):
    account = current_account(request)
    if account is None:
        return set()
    return set(account.shortcut_set.values_list("service_id", flat=True))


def _client_ip(request):
    if settings.BEHIND_PROXY:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            # La dernière adresse est celle ajoutée par notre propre proxy.
            return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


def _throttled(request, scope, limit=10, window=15 * 60):
    key = f"throttle:{scope}:{_client_ip(request)}"
    attempts = cache.get(key, 0)
    if attempts >= limit:
        return True
    cache.set(key, attempts + 1, window)
    return False


def _safe_next(request, fallback):
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()):
        return target
    return fallback


# --- Pages

def home(request):
    return render(request, "core/home.html", {
        "services": Service.objects.filter(active=True)[:6],
        "shortcut_ids": _shortcut_ids(request),
        "books": GuideBook.objects.all()[:4],
        "posts": latest_posts(3),
    })


def je_vois(request):
    new_number = request.session.pop(NEW_NUMBER_KEY, None)
    account = current_account(request)
    shortcuts = account.shortcut_set.select_related("service") if account else []
    return render(request, "core/je_vois.html", {
        "account": account,
        "shortcuts": shortcuts,
        "new_number": format_number(new_number) if new_number else None,
        "pending": pending_anonymous_account(request),
    })


def vous_voyez(request):
    return render(request, "core/vous_voyez.html", {
        "services": Service.objects.filter(active=True),
        "shortcut_ids": _shortcut_ids(request),
    })


def ils_et_elles_voient(request):
    return render(request, "core/ils_et_elles_voient.html", {
        "donors": Donor.objects.filter(public=True),
    })


# --- Comptes anonymes

@require_POST
def create_anonymous(request):
    if current_account(request) is None:
        current_account(request, create=True)
        messages.success(request, "Compte anonyme créé.")
    return redirect("core:je_vois")


@require_POST
def recover_anonymous(request):
    if _throttled(request, "recover"):
        messages.error(request, "Trop d'essais depuis cet appareil. Réessayez dans un quart d'heure.")
        return redirect("core:je_vois")
    account = Account.find_by_number(request.POST.get("number", ""))
    if account is None:
        messages.error(request, "Aucun compte ne correspond à ce numéro. Vérifiez les 16 chiffres.")
    else:
        request.session[SESSION_KEY] = account.pk
        messages.success(request, "Compte retrouvé. Vos raccourcis sont de retour.")
    return redirect("core:je_vois")


@require_POST
def forget_anonymous(request):
    request.session.pop(SESSION_KEY, None)
    messages.success(request, "Ce compte n'est plus ouvert sur cet appareil. Votre numéro permet de le retrouver.")
    return redirect("core:home")


@require_POST
@login_required
def link_anonymous(request):
    pending = pending_anonymous_account(request)
    if pending is not None:
        current_account(request).absorb(pending)
        request.session.pop(SESSION_KEY, None)
        messages.success(request, "Vos raccourcis anonymes ont rejoint votre compte.")
    return redirect("core:je_vois")


# --- Raccourcis

@require_POST
def toggle_shortcut(request, slug):
    service = get_object_or_404(Service, slug=slug, active=True)
    had_account = current_account(request) is not None
    account = current_account(request, create=True)

    shortcut = Shortcut.objects.filter(account=account, service=service).first()
    if shortcut:
        shortcut.delete()
        added = False
        text = f"« {service.name} » retiré de vos raccourcis."
    else:
        Shortcut.objects.create(account=account, service=service)
        added = True
        text = f"« {service.name} » ajouté à vos raccourcis."

    new_number = None
    if not had_account and account.is_anonymous_only:
        new_number = request.session.pop(NEW_NUMBER_KEY, None)

    if _is_htmx(request):
        return render(request, "core/partials/shortcut_response.html", {
            "service": service,
            "added": added,
            "toast": text,
            "new_number": format_number(new_number) if new_number else None,
            "next": request.POST.get("next", ""),
        })

    if new_number:
        # Sans JavaScript : on passe par « je Vois » pour montrer le numéro une fois.
        request.session[NEW_NUMBER_KEY] = new_number
        messages.success(request, text)
        return redirect("core:je_vois")
    messages.success(request, text)
    return redirect(_safe_next(request, reverse("core:vous_voyez")))
