import calendar
import logging
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from smtplib import SMTPException
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMessage
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import date as format_date
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import Truncator, slugify
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .accounts import NEW_NUMBER_KEY, SESSION_KEY, current_account, pending_anonymous_account
from .forms import ContactMessageForm, ContributionForm, DirectoryEntryForm, EventForm
from .menu import ENTRIES, GROUPS, entry_href
from .models import (
    Account, Audience, Contribution, DirectoryEntry, DirectorySector, EntryMessage, EntrySubscription, Event,
    EventInterest, EventManagementRequest, GuideBook, Membership, OwnershipClaim, Service, Shortcut, Tag,
    format_number,
)

from wagtail.models import Locale

logger = logging.getLogger(__name__)


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


def _month_calendar(request):
    """
    Calendrier mensuel de l'agenda pour la home (voir home) : mois demandé via ?mois=
    (AAAA-MM), semaines complètes du lundi au dimanche, y compris les jours des mois
    voisins pour compléter la grille — sans évènement dessus, juste pour l'alignement.
    """
    today = timezone.localdate()
    try:
        year, month = (int(part) for part in request.GET.get("mois", "").split("-"))
        first_of_month = date(year, month, 1)
    except (TypeError, ValueError):
        first_of_month = date(today.year, today.month, 1)

    month_dates = list(calendar.Calendar(firstweekday=0).itermonthdates(first_of_month.year, first_of_month.month))
    events_by_day = {}
    for event in Event.objects.filter(
        public=True, start__date__gte=month_dates[0], start__date__lte=month_dates[-1],
    ).order_by("start"):
        events_by_day.setdefault(event.start.date(), []).append(event)

    weeks = [
        [
            {
                "date": day,
                "in_month": day.month == first_of_month.month,
                "today": day == today,
                "events": events_by_day.get(day, []),
            }
            for day in month_dates[i:i + 7]
        ]
        for i in range(0, len(month_dates), 7)
    ]
    previous_month = (first_of_month.replace(day=1) - timedelta(days=1)).replace(day=1)
    next_month = (first_of_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    return {
        "weeks": weeks,
        "month_label": first_of_month,
        "previous_month": previous_month.strftime("%Y-%m"),
        "next_month": next_month.strftime("%Y-%m"),
    }


# --- Pages

def home(request):
    from cms.models import BlogPostPage, PolePage
    
    active_lang = Locale.get_active()
    
    recent_entries = DirectoryEntry.objects.filter(
        visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=True,
    ).select_related("sector").order_by("-pk")[:4]
    # Sous-titre qui défile dans les .hero-quicklinks (home.html), mis en avant
    # d'abord — sans JS, le premier élément (déjà le plus pertinent grâce à ce tri)
    # reste affiché seul, statique. DirectoryEntry n'a pas de notion de mise en avant
    # ni de date de création : recent_entries (-pk, déjà calculé ci-dessus) en tient lieu.
    quicklink_posts = BlogPostPage.objects.live().filter(locale_id=active_lang.id).order_by("-featured", "-date")[:4]
    quicklink_events = Event.objects.filter(
        public=True, start__gte=timezone.now(),
    ).order_by("-featured", "start")[:4]
    recent_posts = BlogPostPage.objects.live().filter(locale_id=active_lang.id).order_by("-date")[:3]

    return render(request, "core/home.html", {
        "services": Service.objects.filter(active=True)[:6],
        "shortcut_ids": _shortcut_ids(request),
        "books": GuideBook.objects.filter(published=True)[:4],
        "posts": recent_posts,
        "audiences": Audience.objects.all(),
        "poles": PolePage.objects.live().filter(locale_id=active_lang.id).order_by("path"),
        "recent_entries": recent_entries,
        "agenda_calendar": _month_calendar(request),
        "next_event": Event.objects.filter(public=True, start__gte=timezone.now()).order_by("start").first(),
        "quicklink_entry_texts": [e.name for e in recent_entries],
        "quicklink_post_texts": [str(Truncator(p.title).chars(40)) for p in quicklink_posts],
        "quicklink_event_texts": [
            f"{format_date(e.start, 'j M')} — {Truncator(e.title).chars(30)}" for e in quicklink_events
        ],
    })


def _text_lead(html_or_text, max_length=200):
    """Un texte d'ouverture à défaut d'en avoir un : les premiers mots d'un champ plus
    long (corps de page, description…), balises HTML retirées s'il y en a."""
    if not html_or_text:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(html_or_text))
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0] + "…"
    return text


def _page_search_lead(page):
    for attr in ("lead", "intro", "excerpt", "search_description"):
        value = getattr(page, attr, "")
        if value:
            return _text_lead(value)
    return _text_lead(getattr(page, "body", ""))


def _page_search_image(page):
    for attr in ("featured_image", "icon"):
        image = getattr(page, attr, None)
        if image:
            return image
    return None


def search(request):
    query = request.GET.get("q", "").strip()
    pages = entries = events = services = wiki_results = []
    
    active_lang = Locale.get_active()
    
    if query:
        from wagtail.models import Page

        # .search() renvoie des Page génériques (pas de .specific() sur ses résultats) :
        # on récupère les instances spécifiques à part, en gardant l'ordre de pertinence.
        found = list(Page.objects.live().filter(locale_id=active_lang.id).search(query)[:20])
        specific_by_id = {p.pk: p for p in Page.objects.specific().filter(pk__in=[p.pk for p in found])}
        pages = [specific_by_id[p.pk] for p in found if p.pk in specific_by_id]
        for page in pages:
            page.search_lead = _page_search_lead(page)
            page.search_image = _page_search_image(page)

        entries = list(DirectoryEntry.objects.filter(
            Q(name__icontains=query) | Q(tagline__icontains=query) | Q(description__icontains=query),
            visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=True,
        )[:20])
        for entry in entries:
            entry.search_lead = entry.tagline or _text_lead(entry.description)

        events = list(Event.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query) | Q(location__icontains=query),
            public=True,
        )[:20])
        for event in events:
            event.search_lead = _text_lead(event.description) or event.location

        services = list(Service.objects.filter(
            Q(name__icontains=query) | Q(summary__icontains=query) | Q(description__icontains=query),
            active=True,
        )[:20])

        from .wikijs import search as wikijs_search

        wiki_results = wikijs_search(query)
    return render(request, "core/search.html", {
        "query": query,
        "pages": pages,
        "entries": entries,
        "events": events,
        "services": services,
        "wiki_results": wiki_results,
        "total": len(pages) + len(entries) + len(events) + len(services) + len(wiki_results),
    })


def tag_list(request):
    tags = Tag.objects.all()
    return render(request, "core/tag_list.html", {"tags": tags})


def tag_detail(request, slug):
    
    active_lang = Locale.get_active()
    
    tag = get_object_or_404(Tag, slug=slug)
    entries = tag.directory_entries.filter(visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=True)
    services = tag.services.filter(active=True)
    events = tag.events.filter(public=True, start__gte=timezone.now()).order_by("start")
    from cms.models import BlogPostPage, PolePage, ProjectPage

    posts = BlogPostPage.objects.live().filter(tags=tag).filter(locale_id=active_lang.id).order_by("-date")
    poles = PolePage.objects.live().filter(locale_id=active_lang.id).filter(tags=tag)
    projects = ProjectPage.objects.live().filter(locale_id=active_lang.id).filter(tags=tag)
    return render(request, "core/tag_detail.html", {
        "tag": tag,
        "entries": entries,
        "services": services,
        "events": events,
        "posts": posts,
        "poles": poles,
        "projects": projects,
        "total": (
            entries.count() + services.count() + events.count() + posts.count() + poles.count() + projects.count()
        ),
    })


def _process_contact_form(request, throttle_scope, recipient_email):
    """
    Partie commune du formulaire de contact (author_detail, entry_detail) : throttle,
    validation, piège à robots, envoi par e-mail. Renvoie (form, cleaned_data,
    email_sent) — cleaned_data reste None tant qu'il n'y a rien de plus à faire ; une
    fois non-None, à l'appelant de créer sa propre trace (AuthorMessage/EntryMessage, à
    condition que cleaned_data["website"] soit vide — voir ContactMessageForm) et de
    rediriger. email_sent est False si le message a été validé et enregistré mais que
    l'envoi immédiat par e-mail a échoué (serveur SMTP injoignable/mal configuré) — la
    trace existe quand même, seul l'e-mail est manqué.
    """
    form = ContactMessageForm()
    if not (recipient_email and request.method == "POST"):
        return form, None, True
    if _throttled(request, throttle_scope, limit=5):
        messages.error(request, _("Trop de messages envoyés récemment depuis cet appareil. Réessayez plus tard."))
        return form, None, True
    form = ContactMessageForm(request.POST)
    if not form.is_valid():
        return form, None, True
    email_sent = True
    if not form.cleaned_data["website"]:
        try:
            EmailMessage(
                subject=_("Message via lesgrandsvoisins.com de %(name)s") % {
                    "name": form.cleaned_data["sender_name"] or form.cleaned_data["sender_email"],
                },
                body=form.cleaned_data["message"],
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email],
                reply_to=[form.cleaned_data["sender_email"]],
            ).send()
        except (OSError, SMTPException) as exc:
            # Un serveur SMTP mal configuré/injoignable ne doit jamais faire planter la
            # requête (ni, pire, bloquer tout un worker gunicorn) — le message reste
            # quand même enregistré (AuthorMessage/EntryMessage, côté appelant) pour ne
            # pas le perdre ; seul l'e-mail immédiat échoue.
            logger.warning("Échec de l'envoi du message de contact à %s : %s", recipient_email, exc)
            email_sent = False
    return form, form.cleaned_data, email_sent


def author_detail(request, pk):
    from cms.models import Author, AuthorMessage, BlogPostPage, ContentPage
    
    active_lang = Locale.get_active()

    author = get_object_or_404(Author, pk=pk)
    posts = BlogPostPage.objects.live().filter(author=author).filter(locale_id=active_lang.id).order_by("-date")
    pages = ContentPage.objects.live().filter(author=author).filter(locale_id=active_lang.id).order_by("-first_published_at")

    form, sent, email_sent = _process_contact_form(request, "author_contact", author.email)
    if sent is not None:
        if not sent["website"]:
            AuthorMessage.objects.create(
                author=author, sender_name=sent["sender_name"], sender_email=sent["sender_email"],
                message=sent["message"],
            )
        if email_sent:
            messages.success(request, _("Message envoyé à %(name)s.") % {"name": author.name})
        else:
            messages.error(
                request,
                _("Votre message a été enregistré, mais son envoi par e-mail a échoué. Réessayez plus tard."),
            )
        return redirect("core:author_detail", pk=author.pk)
    return render(request, "core/author_detail.html", {
        "author": author, "posts": posts, "pages": pages, "form": form,
    })


def _is_administration(user):
    return user.is_authenticated and user.groups.filter(name="Administration").exists()


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
        "managed_events": acc.managed_events.order_by("-start") if acc else [],
        "new_number": format_number(new_number) if new_number else None,
        "pending": pending_anonymous_account(request),
        "is_administration": _is_administration(request.user),
        "contribution_form": ContributionForm(),
    })


def mes_dons(request):
    acc = current_account(request)
    if acc is None:
        return redirect("core:account")
    return render(request, "core/mes_dons.html", {
        "account": acc,
        "account_contributions": acc.contributions.all(),
        "contribution_form": ContributionForm(),
    })


@require_POST
def faire_don(request):
    acc = current_account(request, create=True)
    form = ContributionForm(request.POST)
    if form.is_valid():
        amount = form.cleaned_data["amount"]
        method = form.cleaned_data["method"]
        date = form.cleaned_data["date"]
        note = form.cleaned_data["note"]
        kind = form.cleaned_data["kind"]
        if kind in (ContributionForm.KIND_PLEDGE, ContributionForm.KIND_BOTH):
            # Une promesse n'a rien à valider : approved=True dès la création, à
            # l'inverse d'un paiement (voir Contribution.approved).
            Contribution.objects.create(
                account=acc, kind=Contribution.PLEDGE, amount=amount, method=method, date=date, note=note,
                approved=True,
            )
        if kind in (ContributionForm.KIND_PAYMENT, ContributionForm.KIND_BOTH):
            Contribution.objects.create(
                account=acc, kind=Contribution.PAYMENT, amount=amount, method=method, date=date, note=note,
            )
        messages.success(request, _("Merci ! Votre contribution a été enregistrée."))
        return redirect(f"{reverse('core:faire_don_merci')}?{urlencode({'amount': amount, 'method': method, 'kind': kind})}")
    messages.error(request, _("Le formulaire de don contient une erreur : montant ou date invalide."))
    return redirect(f"{reverse('core:account')}#fin-title")


def faire_don_merci(request):
    from cms.models import DonationPage
    
    active_lang = Locale.get_active()
    

    try:
        amount = Decimal(request.GET.get("amount", ""))
    except InvalidOperation:
        amount = None
    method = request.GET.get("method", "")
    kind = request.GET.get("kind", "")

    donation_service = (
        Service.objects.filter(slug__in=["helloasso", "paypal", "stripe"], slug=method, active=True).first()
    )
    # PayPal accepte le montant en paramètre d'URL, contrairement à HelloAsso/Stripe
    # (leurs liens ne sont pas garantis le permettre) — on ne le tente donc que là.
    donation_link = donation_service.url if donation_service else ""
    if donation_service and method == "paypal" and amount:
        sep = "&" if "?" in donation_link else "?"
        donation_link = f"{donation_link}{sep}amount={amount}"

    return render(request, "core/faire_don_merci.html", {
        "amount": amount,
        "method": method,
        "method_display": dict(Contribution.METHODS).get(method, method),
        "kind": kind,
        "awaiting_validation": kind in (ContributionForm.KIND_PAYMENT, ContributionForm.KIND_BOTH),
        "donation_service": donation_service,
        "donation_link": donation_link,
        "donation_page": DonationPage.objects.live().filter(locale_id=active_lang.id).first(),
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
            visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=True,
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
    (nommés ou anonymes), absent de l'annuaire. Publié : ouvert à tout le monde, mais
    seulement une fois validé par le groupe « Administration » (sinon réservé au
    propriétaire, comme si la fiche était encore non publiée).
    """
    is_owner = acc is not None and entry.owner_id == acc.id
    if is_owner:
        return
    if entry.visibility == DirectoryEntry.VISIBILITY_DRAFT:
        raise Http404
    if entry.visibility == DirectoryEntry.VISIBILITY_PROTECTED and acc is None:
        raise Http404
    if entry.visibility == DirectoryEntry.VISIBILITY_PUBLIC and not entry.approved:
        raise Http404


def entry_detail(request, slug):
    entry = get_object_or_404(DirectoryEntry, slug=slug)
    acc = current_account(request, create=request.user.is_authenticated)
    _check_entry_visible(entry, acc)
    # Une demande lancée avant connexion (claim_entry_ownership) attend ici la session
    # Keycloak qui vient de s'établir, pour se terminer d'elle-même.
    if request.user.is_authenticated and request.session.get(PENDING_CLAIM_KEY) == slug:
        del request.session[PENDING_CLAIM_KEY]
        if entry.owner_id is None:
            _create_ownership_claim(request, entry, acc)
    my_subscription = acc.entrysubscription_set.filter(entry=entry).first() if acc else None
    my_claim = None
    if request.user.is_authenticated and entry.owner_id is None:
        my_claim = OwnershipClaim.objects.filter(entry=entry, account=acc).first()

    form, sent, email_sent = _process_contact_form(request, "entry_contact", entry.email)
    if sent is not None:
        if not sent["website"]:
            EntryMessage.objects.create(
                entry=entry, sender_name=sent["sender_name"], sender_email=sent["sender_email"],
                message=sent["message"],
            )
        if email_sent:
            messages.success(request, _("Message envoyé à %(name)s.") % {"name": entry.name})
        else:
            messages.error(
                request,
                _("Votre message a été enregistré, mais son envoi par e-mail a échoué. Réessayez plus tard."),
            )
        return redirect("core:entry_detail", slug=entry.slug)

    return render(request, "core/directory_entry.html", {
        "entry": entry,
        "my_subscription": my_subscription,
        "my_claim": my_claim,
        "contact_form": form,
    })


PENDING_CLAIM_KEY = "voisinternet_pending_ownership_claim"


def _create_ownership_claim(request, entry, acc):
    __, created = OwnershipClaim.objects.get_or_create(entry=entry, account=acc)
    if created:
        messages.success(
            request,
            _("Demande envoyée : un administrateur va l'examiner avant de vous rendre responsable de cette fiche."),
        )
    else:
        messages.info(request, _("Vous avez déjà demandé à être responsable de cette fiche."))


@require_POST
def claim_entry_ownership(request, slug):
    # Réservé aux comptes nominatifs (Keycloak), mais pas besoin d'être déjà connecté
    # pour LANCER la demande : sans session authentifiée, on la met de côté et on invite
    # à se connecter — elle se termine d'elle-même au retour (voir entry_detail), une
    # fois la session Keycloak établie.
    entry = get_object_or_404(DirectoryEntry, slug=slug)
    if entry.owner_id is not None:
        raise Http404

    if not request.user.is_authenticated:
        if not settings.OIDC_ENABLED:
            raise Http404
        request.session[PENDING_CLAIM_KEY] = entry.slug
        next_url = reverse("core:entry_detail", args=[entry.slug])
        messages.info(request, _("Connectez-vous pour finaliser votre demande de responsabilité de cette fiche."))
        login_url = f"{reverse('oidc_authentication_init')}?{urlencode({'next': next_url})}"
        return redirect(login_url)

    acc = current_account(request, create=True)
    _create_ownership_claim(request, entry, acc)
    return redirect(reverse("core:entry_detail", args=[entry.slug]))


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
        # Pré-remplir une nouvelle fiche avec ce que Keycloak sait déjà de la personne
        # (nom, courriel), pour un compte nominatif — lui évite de les retaper alors
        # qu'elle vient de se connecter avec. Rien à pré-remplir pour un compte anonyme.
        initial = {}
        if acc.user_id:
            if acc.user.get_full_name():
                initial["name_fr"] = acc.user.get_full_name()
            if acc.user.email:
                initial["email"] = acc.user.email
        form = DirectoryEntryForm(initial=initial)
    return render(request, "core/mes_fiches.html", {
        "entries": acc.directory_entries.order_by("name"),
        "subscriptions": acc.entrysubscription_set.select_related("entry").order_by("entry__name"),
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
def toggle_subscription_notify(request, slug):
    acc = current_account(request)
    sub = EntrySubscription.objects.filter(account=acc, entry__slug=slug).first() if acc else None
    if sub is None:
        raise Http404
    sub.notify_email = not sub.notify_email
    sub.save(update_fields=["notify_email"])
    return redirect(_safe_next(request, reverse("core:mes_fiches")))


@require_POST
def toggle_publication(request, slug):
    acc = current_account(request)
    entry = get_object_or_404(DirectoryEntry, slug=slug, owner=acc) if acc else None
    if entry is None:
        raise Http404
    if entry.visibility == DirectoryEntry.VISIBILITY_PUBLIC:
        was_approved = entry.approved
        entry.visibility = DirectoryEntry.VISIBILITY_DRAFT
        entry.approved = False
        messages.success(request, _("Fiche dépubliée.") if was_approved else _("Demande de publication annulée."))
    else:
        entry.visibility = DirectoryEntry.VISIBILITY_PUBLIC
        entry.approved = False
        messages.success(
            request,
            _("Fiche envoyée pour validation : elle sera publique une fois validée par un administrateur."),
        )
    entry.save(update_fields=["visibility", "approved"])
    return redirect(_safe_next(request, reverse("core:entry_detail", args=[entry.slug])))


def agenda(request):
    now = timezone.now()
    return render(request, "core/agenda.html", {
        "upcoming_events": Event.objects.filter(public=True, start__gte=now),
        "past_events": Event.objects.filter(public=True, start__lt=now).order_by("-start")[:5],
    })


PENDING_EVENT_MANAGEMENT_KEY = "voisinternet_pending_event_management_request"


def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk)
    acc = current_account(request, create=request.user.is_authenticated)
    is_manager = acc is not None and event.managers.filter(pk=acc.pk).exists()
    # Un évènement non publié reste réservé à ses responsables (self-service, en attente
    # de publication par le groupe « Administration ») — comme une fiche d'annuaire non
    # publiée reste réservée à son propriétaire (_check_entry_visible).
    if not event.public and not is_manager:
        raise Http404
    # Une demande lancée avant connexion (claim_event_management) attend ici la session
    # Keycloak qui vient de s'établir, pour se terminer d'elle-même.
    if request.user.is_authenticated and request.session.get(PENDING_EVENT_MANAGEMENT_KEY) == event.pk:
        del request.session[PENDING_EVENT_MANAGEMENT_KEY]
        _create_event_management_request(request, event, acc)
    my_management_request = None
    if request.user.is_authenticated and not is_manager:
        my_management_request = EventManagementRequest.objects.filter(event=event, account=acc).first()
    my_interest = EventInterest.objects.filter(event=event, account=acc).first() if acc else None
    return render(request, "core/event_detail.html", {
        "event": event,
        "is_manager": is_manager,
        "my_management_request": my_management_request,
        "my_interest": my_interest,
        "previous_event": Event.objects.filter(public=True, start__lt=event.start).order_by("-start").first(),
        "next_event": Event.objects.filter(public=True, start__gt=event.start).order_by("start").first(),
    })


@require_POST
def toggle_event_interest(request, pk):
    event = get_object_or_404(Event, pk=pk, public=True)
    acc = current_account(request, create=True)
    level = request.POST.get("level") or EventInterest.INTERESTED
    if level not in dict(EventInterest.LEVEL_CHOICES):
        raise Http404
    interest = EventInterest.objects.filter(account=acc, event=event).first()
    if interest is None:
        EventInterest.objects.create(account=acc, event=event, level=level)
        messages.success(request, _("Intérêt enregistré pour « %(title)s ».") % {"title": event.title})
    elif interest.level == level:
        interest.delete()
        messages.success(request, _("Intérêt retiré pour « %(title)s ».") % {"title": event.title})
    else:
        interest.level = level
        interest.save(update_fields=["level"])
        messages.success(request, _("Intention mise à jour pour « %(title)s ».") % {"title": event.title})
    return redirect(_safe_next(request, reverse("core:event_detail", args=[event.pk])))


@require_POST
def toggle_event_interest_notify(request, pk):
    acc = current_account(request)
    interest = EventInterest.objects.filter(account=acc, event_id=pk).first() if acc else None
    if interest is None:
        raise Http404
    interest.notify_email = not interest.notify_email
    interest.save(update_fields=["notify_email"])
    return redirect(_safe_next(request, reverse("core:mes_evenements")))


def _create_event_management_request(request, event, acc):
    __, created = EventManagementRequest.objects.get_or_create(event=event, account=acc)
    if created:
        messages.success(
            request,
            _("Demande envoyée : un administrateur va l'examiner avant de vous rendre responsable de cet évènement."),
        )
    else:
        messages.info(request, _("Vous avez déjà demandé à gérer cet évènement."))


@require_POST
def claim_event_management(request, pk):
    # Même logique que claim_entry_ownership : pas besoin d'être déjà connecté pour
    # LANCER la demande — sans session authentifiée, on la met de côté et on invite à se
    # connecter, elle se termine d'elle-même au retour (voir event_detail).
    event = get_object_or_404(Event, pk=pk, public=True)

    if not request.user.is_authenticated:
        if not settings.OIDC_ENABLED:
            raise Http404
        request.session[PENDING_EVENT_MANAGEMENT_KEY] = event.pk
        next_url = reverse("core:event_detail", args=[event.pk])
        messages.info(request, _("Connectez-vous pour finaliser votre demande de gestion de cet évènement."))
        login_url = f"{reverse('oidc_authentication_init')}?{urlencode({'next': next_url})}"
        return redirect(login_url)

    acc = current_account(request, create=True)
    _create_event_management_request(request, event, acc)
    return redirect(reverse("core:event_detail", args=[event.pk]))


def mes_evenements(request):
    acc = current_account(request, create=True)
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            base_slug = slugify(event.title) or "evenement"
            slug = base_slug
            suffix = 1
            while Event.objects.filter(slug=slug).exists():
                suffix += 1
                slug = f"{base_slug}-{suffix}"
            event.slug = slug
            event.public = False
            event.save()
            form.save_m2m()
            event.managers.add(acc)
            messages.success(request, _("Évènement créé : il reste réservé à ses responsables tant que le "
                                         "groupe « Administration » ne l'a pas publié."))
            return redirect("core:mes_evenements")
    else:
        form = EventForm()
    return render(request, "core/mes_evenements.html", {
        "events": acc.managed_events.order_by("-start"),
        "interests": acc.event_interests.select_related("event").order_by("event__start"),
        "form": form,
    })


def evenement_modifier(request, pk):
    acc = current_account(request)
    event = get_object_or_404(Event, pk=pk, managers=acc) if acc else None
    if event is None:
        return redirect("core:mes_evenements")
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, _("Évènement mis à jour."))
            return redirect("core:mes_evenements")
    else:
        form = EventForm(instance=event)
    return render(request, "core/evenement_modifier.html", {"form": form, "event": event})


@require_POST
def evenement_supprimer(request, pk):
    acc = current_account(request)
    if acc:
        acc.managed_events.filter(pk=pk).delete()
        messages.success(request, _("Évènement supprimé."))
    return redirect("core:mes_evenements")


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
        new_shortcut = Shortcut.objects.create(
            account=account, service=service, position=account.shortcut_set.count(),
        )
        added = True
        if new_shortcut.approved:
            text = _("« %(name)s » ajouté à vos raccourcis.") % {"name": service.name}
        else:
            text = _(
                "« %(name)s » ajouté à vos raccourcis, en attente de validation par un administrateur."
            ) % {"name": service.name}

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


def administration(request):
    """
    Tableau de bord réservé au groupe « Administration » (core.migrations.0019, 0028) :
    validation des demandes de responsabilité de fiche et de gestion d'évènement, et
    bascule rapide de la publication/mise en avant des évènements — sans donner accès à
    l'admin Django (qui exige is_staff, jamais attribué automatiquement à ce groupe).
    """
    if not _is_administration(request.user):
        raise PermissionDenied
    return render(request, "core/administration.html", {
        "pending_claims": OwnershipClaim.objects.filter(approved__isnull=True).select_related("entry", "account"),
        "pending_event_requests": EventManagementRequest.objects.filter(
            approved__isnull=True,
        ).select_related("event", "account"),
        "events": Event.objects.order_by("-start"),
        # Publication demandée (views.toggle_publication) mais pas encore validée.
        "pending_entries": DirectoryEntry.objects.filter(
            visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=False,
        ).select_related("owner"),
        # Paiement auto-déclaré (views.faire_don) en attente de validation — une
        # promesse, elle, est déjà approuvée dès sa création (Contribution.approved).
        "pending_contributions": Contribution.objects.filter(
            kind=Contribution.PAYMENT, approved__isnull=True,
        ).select_related("account"),
    })


@require_POST
def administration_review_claim(request, pk):
    if not _is_administration(request.user):
        raise PermissionDenied
    claim = get_object_or_404(OwnershipClaim, pk=pk, approved__isnull=True)
    claim.approved = request.POST.get("decision") == "approve"
    claim.save()
    return redirect("core:administration")


@require_POST
def administration_review_event_request(request, pk):
    if not _is_administration(request.user):
        raise PermissionDenied
    event_request = get_object_or_404(EventManagementRequest, pk=pk, approved__isnull=True)
    event_request.approved = request.POST.get("decision") == "approve"
    event_request.save()
    return redirect("core:administration")


@require_POST
def administration_toggle_event(request, pk):
    if not _is_administration(request.user):
        raise PermissionDenied
    field = request.POST.get("field")
    if field not in ("public", "featured"):
        raise Http404
    event = get_object_or_404(Event, pk=pk)
    setattr(event, field, not getattr(event, field))
    event.save(update_fields=[field])
    return redirect("core:administration")


@require_POST
def administration_review_entry(request, slug):
    if not _is_administration(request.user):
        raise PermissionDenied
    entry = get_object_or_404(
        DirectoryEntry, slug=slug, visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=False,
    )
    if request.POST.get("decision") == "approve":
        entry.approved = True
    else:
        entry.visibility = DirectoryEntry.VISIBILITY_DRAFT
    entry.save()
    return redirect("core:administration")


@require_POST
def administration_review_contribution(request, pk):
    if not _is_administration(request.user):
        raise PermissionDenied
    contribution = get_object_or_404(Contribution, pk=pk, kind=Contribution.PAYMENT, approved__isnull=True)
    contribution.approved = request.POST.get("decision") == "approve"
    contribution.save()
    return redirect("core:administration")
