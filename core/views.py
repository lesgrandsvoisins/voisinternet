from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .accounts import NEW_NUMBER_KEY, SESSION_KEY, current_account, pending_anonymous_account
from .forms import DirectoryEntryForm
from .menu import ENTRIES, GROUPS, entry_href
from .models import (
    Account, Audience, Contribution, DirectoryEntry, DirectorySector, EntrySubscription, Event, GuideBook,
    Membership, Service, Shortcut, format_number,
)

# Chapeau de présentation pour chaque page intermédiaire (une par groupe du menu).
GROUP_PAGE_INTROS = {
    "reperes": _("Les rendez-vous et les ressources pour s'y retrouver dans la communauté."),
    "poles": _("Nos trois pôles d'action, portés ensemble par les bénévoles."),
    "association": _("Nous rejoindre, nous soutenir, nous contacter."),
}


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
    from cms.models import BlogPostPage

    return render(request, "core/home.html", {
        "services": Service.objects.filter(active=True)[:6],
        "shortcut_ids": _shortcut_ids(request),
        "books": GuideBook.objects.filter(published=True)[:4],
        "posts": BlogPostPage.objects.live().order_by("-date")[:3],
        "audiences": Audience.objects.all(),
    })


def account(request):
    new_number = request.session.pop(NEW_NUMBER_KEY, None)
    acc = current_account(request)
    shortcuts = acc.shortcut_set.select_related("service").order_by(
        "position", "service__order", "service__name",
    ) if acc else []
    memberships = acc.membership_set.select_related("audience").order_by(
        "position", "audience__order", "audience__name",
    ) if acc else []
    return render(request, "core/account.html", {
        "account": acc,
        "account_contributions": acc.contributions.all() if acc else [],
        "shortcuts": shortcuts,
        "memberships": memberships,
        "owned_entries": acc.directory_entries.order_by("name") if acc else [],
        "new_number": format_number(new_number) if new_number else None,
        "pending": pending_anonymous_account(request),
    })


def raccourcis(request):
    acc = current_account(request)
    if acc is None:
        return redirect("core:account")
    shortcuts = acc.shortcut_set.select_related("service").order_by("position", "service__order", "service__name")
    shortcut_ids = set(shortcuts.values_list("service_id", flat=True))
    # Reste dans la liste une fois ajouté (bouton « Ajouté », qui permet de le retirer) :
    # la carte ne doit pas disparaître d'un coup sous le pointeur au moment du clic.
    available_services = Service.objects.filter(active=True).order_by("order", "name")
    return render(request, "core/raccourcis.html", {
        "account": acc,
        "shortcuts": shortcuts,
        "shortcut_ids": shortcut_ids,
        "available_services": available_services,
    })


def groupes(request):
    acc = current_account(request)
    if acc is None:
        return redirect("core:account")
    memberships = acc.membership_set.select_related("audience").order_by("position", "audience__order", "audience__name")
    membership_ids = set(memberships.values_list("audience_id", flat=True))
    available_audiences = Audience.objects.exclude(pk__in=membership_ids).order_by("order", "name")
    return render(request, "core/groupes.html", {
        "account": acc,
        "memberships": memberships,
        "membership_ids": membership_ids,
        "available_audiences": available_audiences,
    })


def annuaire(request, secteur=None):
    current = None
    if secteur:
        current = get_object_or_404(DirectorySector, slug=secteur)

    # Liste publique, identique pour tout le monde (l'abonnement de la personne qui
    # regarde est calculé à part, ci-dessous) : on la met en cache un moment plutôt que
    # de la recalculer à chaque visite, comme pour les articles du blog (core/ghost.py).
    cache_key = f"annuaire:entries:{secteur or 'all'}"
    entries = cache.get(cache_key)
    if entries is None:
        qs = DirectoryEntry.objects.filter(
            visibility=DirectoryEntry.VISIBILITY_PUBLIC,
        ).select_related("sector").prefetch_related("audiences", "gallery_photos").order_by("name")
        if current:
            qs = qs.filter(sector=current)
        entries = list(qs)
        cache.set(cache_key, entries, 300)

    acc = current_account(request)
    subscribed_ids = set(acc.entrysubscription_set.values_list("entry_id", flat=True)) if acc else set()
    return render(request, "core/annuaire.html", {
        "entries": entries,
        "sectors": DirectorySector.objects.all(),
        "sector": current,
        "subscribed_ids": subscribed_ids,
    })


def _check_entry_visible(entry, acc):
    """
    Non publié : réservé au propriétaire. Brouillon protégé : réservé aux comptes
    (nommés ou anonymes), absent de l'annuaire. Publié : ouvert à tout le monde.
    """
    is_owner = acc is not None and entry.owner_id == acc.id
    if is_owner:
        return
    if entry.visibility == DirectoryEntry.VISIBILITY_DRAFT:
        raise Http404
    if entry.visibility == DirectoryEntry.VISIBILITY_PROTECTED and acc is None:
        raise Http404


def entry_detail(request, slug):
    entry = get_object_or_404(DirectoryEntry, slug=slug)
    acc = current_account(request)
    _check_entry_visible(entry, acc)
    subscribed = acc.entrysubscription_set.filter(entry=entry).exists() if acc else False
    return render(request, "core/directory_entry.html", {
        "entry": entry,
        "subscribed": subscribed,
    })


def mes_fiches(request):
    acc = current_account(request, create=True)
    if request.method == "POST":
        form = DirectoryEntryForm(request.POST, request.FILES)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.owner = acc
            base_slug = slugify(entry.name) or "fiche"
            slug = base_slug
            suffix = 1
            while DirectoryEntry.objects.filter(slug=slug).exists():
                suffix += 1
                slug = f"{base_slug}-{suffix}"
            entry.slug = slug
            entry.save()
            messages.success(request, _("Fiche créée."))
            return redirect("core:mes_fiches")
    else:
        form = DirectoryEntryForm()
    return render(request, "core/mes_fiches.html", {
        "entries": acc.directory_entries.order_by("name"),
        "form": form,
    })


def fiche_modifier(request, slug):
    acc = current_account(request)
    entry = get_object_or_404(DirectoryEntry, slug=slug, owner=acc) if acc else None
    if entry is None:
        return redirect("core:mes_fiches")
    if request.method == "POST":
        form = DirectoryEntryForm(request.POST, request.FILES, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, _("Fiche mise à jour."))
            return redirect("core:mes_fiches")
    else:
        form = DirectoryEntryForm(instance=entry)
    return render(request, "core/fiche_modifier.html", {"form": form, "entry": entry})


@require_POST
def fiche_supprimer(request, slug):
    acc = current_account(request)
    if acc:
        acc.directory_entries.filter(slug=slug).delete()
        messages.success(request, _("Fiche supprimée."))
    return redirect("core:mes_fiches")


@require_POST
def toggle_subscription(request, slug):
    entry = get_object_or_404(DirectoryEntry, slug=slug)
    acc = current_account(request, create=True)
    _check_entry_visible(entry, acc)
    sub = EntrySubscription.objects.filter(account=acc, entry=entry).first()
    if sub:
        sub.delete()
        text = _("Abonnement à « %(name)s » retiré.") % {"name": entry.name}
    else:
        EntrySubscription.objects.create(account=acc, entry=entry)
        text = _("Abonné à « %(name)s ».") % {"name": entry.name}
    messages.success(request, text)
    return redirect(_safe_next(request, reverse("core:annuaire")))


@require_POST
def toggle_publication(request, slug):
    acc = current_account(request)
    entry = get_object_or_404(DirectoryEntry, slug=slug, owner=acc) if acc else None
    if entry is None:
        raise Http404
    if entry.visibility == DirectoryEntry.VISIBILITY_PUBLIC:
        entry.visibility = DirectoryEntry.VISIBILITY_DRAFT
        messages.success(request, _("Fiche dépubliée."))
    else:
        entry.visibility = DirectoryEntry.VISIBILITY_PUBLIC
        messages.success(request, _("Fiche publiée."))
    entry.save(update_fields=["visibility"])
    return redirect(_safe_next(request, reverse("core:entry_detail", args=[entry.slug])))


def agenda(request):
    now = timezone.now()
    return render(request, "core/agenda.html", {
        "upcoming_events": Event.objects.filter(public=True, start__gte=now),
        "past_events": Event.objects.filter(public=True, start__lt=now).order_by("-start")[:5],
    })


def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk, public=True)
    return render(request, "core/event_detail.html", {"event": event})


def event_ics(request, pk):
    from .ics import event_to_ics

    event = get_object_or_404(Event, pk=pk, public=True)
    response = HttpResponse(event_to_ics(event, request), content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{event.slug or "evenement"}.ics"'
    return response


def group_page(request, key):
    caption = dict(GROUPS).get(key)
    if caption is None:
        raise Http404
    items = [{"entry": e, "href": entry_href(e)} for e in ENTRIES if e.group == key]
    return render(request, "core/group_page.html", {
        "group_caption": caption,
        "group_intro": GROUP_PAGE_INTROS.get(key, ""),
        "items": items,
    })


@require_POST
def markdown_preview(request):
    return render(request, "core/partials/markdown_preview.html", {
        "text": request.POST.get("description_fr", ""),
    })

# --- Comptes anonymes

@require_POST
def create_anonymous(request):
    if current_account(request) is None:
        current_account(request, create=True)
        messages.success(request, _("Compte anonyme créé."))
    return redirect("core:account")


@require_POST
def recover_anonymous(request):
    if _throttled(request, "recover"):
        messages.error(request, _("Trop d'essais depuis cet appareil. Réessayez dans un quart d'heure."))
        return redirect("core:account")
    account = Account.find_by_number(request.POST.get("number", ""))
    if account is None:
        messages.error(request, _("Aucun compte ne correspond à ce numéro. Vérifiez les 16 chiffres."))
    else:
        request.session[SESSION_KEY] = account.pk
        messages.success(request, _("Compte retrouvé. Vos raccourcis sont de retour."))
    return redirect("core:account")


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
    return redirect("core:account")


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
        available_services = Service.objects.filter(active=True).order_by("order", "name")
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
        # Sans JavaScript : on passe par « mon Compte » pour montrer le numéro une fois.
        request.session[NEW_NUMBER_KEY] = new_number
        messages.success(request, text)
        return redirect("core:account")
    messages.success(request, text)
    return redirect(_safe_next(request, reverse("core:raccourcis")))


@require_POST
def reorder_shortcut(request, slug, direction):
    account = current_account(request)
    if account is None:
        if _is_htmx(request):
            return HttpResponse(status=403)
        return redirect("core:raccourcis")

    service = get_object_or_404(Service, slug=slug, active=True)
    shortcut = account.shortcut_set.filter(service=service).first()
    if shortcut is None:
        if _is_htmx(request):
            return HttpResponse(status=404)
        return redirect("core:raccourcis")

    direction = direction.lower()
    if direction not in {"up", "down"}:
        if _is_htmx(request):
            return HttpResponse(status=400)
        return redirect("core:raccourcis")

    shortcuts = list(account.shortcut_set.select_related("service").order_by("position", "service__order", "service__name"))
    index = next((i for i, item in enumerate(shortcuts) if item.pk == shortcut.pk), None)
    if index is None:
        if _is_htmx(request):
            return HttpResponse(status=404)
        return redirect("core:raccourcis")

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

    return redirect("core:raccourcis")


@require_POST
def reorder_shortcuts(request):
    """
    Glisser-déposer (site.js) : reçoit l'ordre complet des slugs de service et réattribue
    les positions en conséquence. Complète les boutons ↑/↓ de reorder_shortcut, qui restent
    la seule façon de réordonner sans JavaScript.
    """
    account = current_account(request)
    if account is None:
        return HttpResponse(status=403)

    shortcuts_by_slug = {sc.service.slug: sc for sc in account.shortcut_set.select_related("service")}
    for position, slug in enumerate(request.POST.get("order", "").split(",")):
        shortcut = shortcuts_by_slug.get(slug)
        if shortcut and shortcut.position != position:
            shortcut.position = position
            shortcut.save(update_fields=["position"])

    return render(request, "core/partials/shortcut_list.html", {
        "shortcuts": account.shortcut_set.select_related("service").order_by("position", "service__order", "service__name"),
    })


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
        return redirect("core:account")
    messages.success(request, text)
    return redirect(_safe_next(request, reverse("core:groupes")))


@require_POST
def reorder_membership(request, slug, direction):
    account = current_account(request)
    if account is None:
        if _is_htmx(request):
            return HttpResponse(status=403)
        return redirect("core:groupes")

    audience = get_object_or_404(Audience, slug=slug)
    membership = account.membership_set.filter(audience=audience).first()
    if membership is None:
        if _is_htmx(request):
            return HttpResponse(status=404)
        return redirect("core:groupes")

    direction = direction.lower()
    if direction not in {"up", "down"}:
        if _is_htmx(request):
            return HttpResponse(status=400)
        return redirect("core:groupes")

    memberships = list(account.membership_set.select_related("audience").order_by("position", "audience__order", "audience__name"))
    index = next((i for i, item in enumerate(memberships) if item.pk == membership.pk), None)
    if index is None:
        if _is_htmx(request):
            return HttpResponse(status=404)
        return redirect("core:groupes")

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

    return redirect("core:groupes")


@require_POST
def reorder_memberships(request):
    """Glisser-déposer (site.js) : voir reorder_shortcuts, même principe pour les groupes."""
    account = current_account(request)
    if account is None:
        return HttpResponse(status=403)

    memberships_by_slug = {m.audience.slug: m for m in account.membership_set.select_related("audience")}
    for position, slug in enumerate(request.POST.get("order", "").split(",")):
        membership = memberships_by_slug.get(slug)
        if membership and membership.position != position:
            membership.position = position
            membership.save(update_fields=["position"])

    return render(request, "core/partials/membership_list.html", {
        "memberships": account.membership_set.select_related("audience").order_by("position", "audience__order", "audience__name"),
    })
