from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .accounts import NEW_NUMBER_KEY, SESSION_KEY, current_account, pending_anonymous_account
from .ghost import latest_posts
from .models import Account, Audience, Donor, GuideBook, Membership, Service, Shortcut, format_number


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
        "audiences": Audience.objects.all(),
    })


def je_vois(request):
    new_number = request.session.pop(NEW_NUMBER_KEY, None)
    account = current_account(request)
    if account:
        shortcuts = account.shortcut_set.select_related("service").order_by("position", "service__order", "service__name")
        shortcut_ids = set(shortcuts.values_list("service_id", flat=True))
        memberships = account.membership_set.select_related("audience").order_by("position", "audience__order", "audience__name")
        membership_ids = set(memberships.values_list("audience_id", flat=True))
    else:
        shortcuts = []
        shortcut_ids = set()
        memberships = []
        membership_ids = set()
    available_services = Service.objects.filter(active=True).exclude(pk__in=shortcut_ids).order_by("order", "name")
    available_audiences = Audience.objects.exclude(pk__in=membership_ids).order_by("order", "name")
    return render(request, "core/je_vois.html", {
        "account": account,
        "shortcuts": shortcuts,
        "shortcut_ids": shortcut_ids,
        "available_services": available_services,
        "memberships": memberships,
        "membership_ids": membership_ids,
        "available_audiences": available_audiences,
        "new_number": format_number(new_number) if new_number else None,
        "pending": pending_anonymous_account(request),
    })


def vous_voyez(request, audience=None):
    current = None
    if audience:
        current = get_object_or_404(Audience, slug=audience)
    return render(request, "core/vous_voyez.html", {
        "audiences": Audience.objects.all(),
        "audience": current,
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
        messages.success(request, _("Compte anonyme créé."))
    return redirect("core:je_vois")


@require_POST
def recover_anonymous(request):
    if _throttled(request, "recover"):
        messages.error(request, _("Trop d'essais depuis cet appareil. Réessayez dans un quart d'heure."))
        return redirect("core:je_vois")
    account = Account.find_by_number(request.POST.get("number", ""))
    if account is None:
        messages.error(request, _("Aucun compte ne correspond à ce numéro. Vérifiez les 16 chiffres."))
    else:
        request.session[SESSION_KEY] = account.pk
        messages.success(request, _("Compte retrouvé. Vos raccourcis sont de retour."))
    return redirect("core:je_vois")


@require_POST
def forget_anonymous(request):
    request.session.pop(SESSION_KEY, None)
    messages.success(request, _("Ce compte n'est plus ouvert sur cet appareil. Votre numéro permet de le retrouver."))
    return redirect("core:home")


@require_POST
@login_required
def link_anonymous(request):
    pending = pending_anonymous_account(request)
    if pending is not None:
        current_account(request).absorb(pending)
        request.session.pop(SESSION_KEY, None)
        messages.success(request, _("Vos raccourcis anonymes ont rejoint votre compte."))
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
        text = _("« %(name)s » retiré de vos raccourcis.") % {"name": service.name}
    else:
        Shortcut.objects.create(account=account, service=service, position=account.shortcut_set.count())
        added = True
        text = _("« %(name)s » ajouté à vos raccourcis.") % {"name": service.name}

    new_number = None
    if not had_account and account.is_anonymous_only:
        new_number = request.session.pop(NEW_NUMBER_KEY, None)

    if _is_htmx(request):
        account = current_account(request)
        shortcut_ids = set(account.shortcut_set.values_list("service_id", flat=True)) if account else set()
        shortcuts = account.shortcut_set.select_related("service").order_by("position", "service__order", "service__name") if account else []
        available_services = Service.objects.filter(active=True).exclude(pk__in=shortcut_ids).order_by("order", "name")
        return render(request, "core/partials/shortcut_response.html", {
            "service": service,
            "added": added,
            "toast": text,
            "new_number": format_number(new_number) if new_number else None,
            "next": request.POST.get("next", ""),
            "shortcuts": shortcuts,
            "available_services": available_services,
            "shortcut_ids": shortcut_ids,
        })

    if new_number:
        # Sans JavaScript : on passe par « je Vois » pour montrer le numéro une fois.
        request.session[NEW_NUMBER_KEY] = new_number
        messages.success(request, text)
        return redirect("core:je_vois")
    messages.success(request, text)
    return redirect(_safe_next(request, reverse("core:je_vois")))


@require_POST
def reorder_shortcut(request, slug, direction):
    account = current_account(request)
    if account is None:
        if _is_htmx(request):
            return HttpResponse(status=403)
        return redirect("core:je_vois")

    service = get_object_or_404(Service, slug=slug, active=True)
    shortcut = account.shortcut_set.filter(service=service).first()
    if shortcut is None:
        if _is_htmx(request):
            return HttpResponse(status=404)
        return redirect("core:je_vois")

    direction = direction.lower()
    if direction not in {"up", "down"}:
        if _is_htmx(request):
            return HttpResponse(status=400)
        return redirect("core:je_vois")

    shortcuts = list(account.shortcut_set.select_related("service").order_by("position", "service__order", "service__name"))
    index = next((i for i, item in enumerate(shortcuts) if item.pk == shortcut.pk), None)
    if index is None:
        if _is_htmx(request):
            return HttpResponse(status=404)
        return redirect("core:je_vois")

    target_index = index - 1 if direction == "up" else index + 1
    if 0 <= target_index < len(shortcuts):
        target = shortcuts[target_index]
        current_position = shortcut.position or index
        target_position = target.position or target_index
        shortcut.position = target_position
        target.position = current_position
        shortcut.save(update_fields=["position"])
        target.save(update_fields=["position"])

    if _is_htmx(request):
        return render(request, "core/partials/shortcut_list.html", {
            "shortcuts": account.shortcut_set.select_related("service").order_by("position", "service__order", "service__name"),
        })

    return redirect("core:je_vois")


# --- Appartenances

@require_POST
def toggle_membership(request, slug):
    audience = get_object_or_404(Audience, slug=slug)
    had_account = current_account(request) is not None
    account = current_account(request, create=True)

    membership = Membership.objects.filter(account=account, audience=audience).first()
    if membership:
        membership.delete()
        added = False
        text = _("« %(name)s » retiré de vos groupes.") % {"name": audience.name}
    else:
        Membership.objects.create(account=account, audience=audience, position=account.membership_set.count())
        added = True
        text = _("« %(name)s » ajouté à vos groupes.") % {"name": audience.name}

    new_number = None
    if not had_account and account.is_anonymous_only:
        new_number = request.session.pop(NEW_NUMBER_KEY, None)

    if _is_htmx(request):
        account = current_account(request)
        membership_ids = set(account.membership_set.values_list("audience_id", flat=True)) if account else set()
        memberships = account.membership_set.select_related("audience").order_by("position", "audience__order", "audience__name") if account else []
        available_audiences = Audience.objects.exclude(pk__in=membership_ids).order_by("order", "name")
        return render(request, "core/partials/membership_response.html", {
            "audience": audience,
            "added": added,
            "toast": text,
            "new_number": format_number(new_number) if new_number else None,
            "next": request.POST.get("next", ""),
            "memberships": memberships,
            "available_audiences": available_audiences,
            "membership_ids": membership_ids,
        })

    if new_number:
        request.session[NEW_NUMBER_KEY] = new_number
        messages.success(request, text)
        return redirect("core:je_vois")
    messages.success(request, text)
    return redirect(_safe_next(request, reverse("core:je_vois")))


@require_POST
def reorder_membership(request, slug, direction):
    account = current_account(request)
    if account is None:
        if _is_htmx(request):
            return HttpResponse(status=403)
        return redirect("core:je_vois")

    audience = get_object_or_404(Audience, slug=slug)
    membership = account.membership_set.filter(audience=audience).first()
    if membership is None:
        if _is_htmx(request):
            return HttpResponse(status=404)
        return redirect("core:je_vois")

    direction = direction.lower()
    if direction not in {"up", "down"}:
        if _is_htmx(request):
            return HttpResponse(status=400)
        return redirect("core:je_vois")

    memberships = list(account.membership_set.select_related("audience").order_by("position", "audience__order", "audience__name"))
    index = next((i for i, item in enumerate(memberships) if item.pk == membership.pk), None)
    if index is None:
        if _is_htmx(request):
            return HttpResponse(status=404)
        return redirect("core:je_vois")

    target_index = index - 1 if direction == "up" else index + 1
    if 0 <= target_index < len(memberships):
        target = memberships[target_index]
        current_position = membership.position or index
        target_position = target.position or target_index
        membership.position = target_position
        target.position = current_position
        membership.save(update_fields=["position"])
        target.save(update_fields=["position"])

    if _is_htmx(request):
        return render(request, "core/partials/membership_list.html", {
            "memberships": account.membership_set.select_related("audience").order_by("position", "audience__order", "audience__name"),
        })

    return redirect("core:je_vois")
