from django.contrib import admin
from modeltranslation.admin import TranslationAdmin, TranslationTabularInline

from .models import (
    Account, Audience, Contribution, DirectoryEntry, DirectoryEntryPhoto, DirectorySector, Donor, EntrySubscription,
    Event, EventInterest, EventManagementRequest, GuideBook,
    Membership, OwnershipClaim, Service, ServiceCategory, Shortcut, Tag,
)

admin.site.site_header = "lesgrandsvoisins.com"
admin.site.site_title = "lesgrandsvoisins.com"
admin.site.index_title = "Administration"


@admin.register(Audience)
class AudienceAdmin(TranslationAdmin):
    list_display = ["name", "who", "partnership", "order"]
    list_editable = ["order"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(TranslationAdmin):
    list_display = ["name", "order"]
    list_editable = ["order"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]


@admin.register(Tag)
class TagAdmin(TranslationAdmin):
    list_display = ["name"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]


@admin.register(Service)
class ServiceAdmin(TranslationAdmin):
    list_display = ["name", "summary", "category", "featured", "active", "requires_approval", "order"]
    list_filter = ["category", "requires_approval"]
    filter_horizontal = ["audiences", "tags"]
    list_editable = ["featured", "active", "order"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name", "summary"]
    autocomplete_fields = ["category"]


@admin.register(Shortcut)
class ShortcutAdmin(admin.ModelAdmin):
    """
    Accessible au groupe « Administration » (core.migrations.0019) pour valider les
    raccourcis en attente (Service.requires_approval) : eux seuls, sans autre droit sur
    core.Account, ont donc besoin d'un accès direct à ce modèle plutôt que par l'inline
    d'AccountAdmin (qui exige la permission sur Account).
    """
    list_display = ["service", "account", "approved", "created"]
    list_filter = ["approved", "service"]
    list_editable = ["approved"]
    autocomplete_fields = ["service", "account"]
    search_fields = ["service__name"]


class ShortcutInline(admin.TabularInline):
    model = Shortcut
    extra = 0
    autocomplete_fields = ["service"]


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["audience"]


class ContributionInline(TranslationTabularInline):
    model = Contribution
    extra = 0
    fields = ["kind", "amount", "method", "date", "tax_deductible", "note_fr"]


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["__str__", "user", "created", "last_seen", "shortcut_count", "membership_count"]
    list_filter = [("user", admin.EmptyFieldListFilter)]
    readonly_fields = ["created", "last_seen"]
    inlines = [ShortcutInline, MembershipInline, ContributionInline]
    # Requis par ShortcutAdmin.autocomplete_fields ci-dessus.
    search_fields = ["user__username", "user__first_name", "user__last_name"]

    @admin.display(description="raccourcis")
    def shortcut_count(self, obj):
        return obj.shortcut_set.count()

    @admin.display(description="appartenances")
    def membership_count(self, obj):
        return obj.membership_set.count()


@admin.register(Contribution)
class ContributionAdmin(TranslationAdmin):
    """Vue d'ensemble de toutes les contributions, tous comptes confondus — l'inline
    d'AccountAdmin ci-dessus reste pratique pour en ajouter une depuis une fiche compte,
    mais ne permet pas de filtrer/rechercher à travers l'ensemble (ex. « toutes les
    promesses non encore payées cette année », « tous les reçus fiscaux à établir »)."""
    list_display = ["account", "kind", "amount", "method", "date", "tax_deductible"]
    list_filter = ["kind", "method", "tax_deductible"]
    list_editable = ["tax_deductible"]
    date_hierarchy = "date"
    search_fields = ["account__user__username", "account__user__first_name", "account__user__last_name", "note"]
    autocomplete_fields = ["account"]


@admin.register(GuideBook)
class GuideBookAdmin(TranslationAdmin):
    list_display = ["title", "url", "order", "published"]
    list_editable = ["order", "published"]


@admin.register(Donor)
class DonorAdmin(TranslationAdmin):
    list_display = ["name", "kind", "public", "since"]
    list_filter = ["kind", "public"]
    list_editable = ["public"]


@admin.register(DirectorySector)
class DirectorySectorAdmin(TranslationAdmin):
    list_display = ["name", "order"]
    list_editable = ["order"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]


class DirectoryEntryPhotoInline(admin.TabularInline):
    model = DirectoryEntryPhoto
    extra = 1


@admin.register(DirectoryEntry)
class DirectoryEntryAdmin(TranslationAdmin):
    """« approved » (validation groupe Administration) reste modifiable même par les
    membres de ce groupe, qui n'ont pas la permission de changer le reste de la fiche
    (contrôlé au niveau du champ n'est pas possible ici, mais le formulaire d'auto-
    édition, core.forms.DirectoryEntryForm, ne l'expose de toute façon jamais)."""
    list_display = ["name", "kind", "sector", "owner", "city", "visibility", "approved", "order"]
    list_filter = ["kind", "sector", "visibility", "approved"]
    list_editable = ["visibility", "approved", "order"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name", "description", "city"]
    autocomplete_fields = ["sector"]
    filter_horizontal = ["audiences", "tags"]
    inlines = [DirectoryEntryPhotoInline]
    fieldsets = [
        (None, {
            "fields": [
                "name", "slug", "kind", "sector", "tags", "audiences", "owner", "visibility", "approved", "layout",
                "order",
            ],
        }),
        ("Présentation", {"fields": ["title", "tagline", "description"]}),
        ("Médias", {"fields": ["logo", "photo_promo", "video_url"]}),
        ("Coordonnées", {"fields": ["email", "phone", "website"]}),
        ("Localisation", {"fields": ["address", "postal_code", "city", "region", "country", "latitude", "longitude"]}),
        ("Appel à l'action", {"fields": ["cta_intro", "cta_label", "cta_link"]}),
    ]


@admin.register(EntrySubscription)
class EntrySubscriptionAdmin(admin.ModelAdmin):
    list_display = ["account", "entry", "notify_email", "created"]
    list_filter = ["notify_email"]
    autocomplete_fields = ["entry"]


@admin.register(EventInterest)
class EventInterestAdmin(admin.ModelAdmin):
    list_display = ["account", "event", "level", "notify_email", "created"]
    list_filter = ["level", "notify_email"]
    autocomplete_fields = ["event"]


@admin.register(OwnershipClaim)
class OwnershipClaimAdmin(admin.ModelAdmin):
    """Accessible au groupe « Administration » (core.migrations.0021) : passer
    « validée » à Oui transfère la fiche (OwnershipClaim.save)."""
    list_display = ["account", "entry", "created", "approved"]
    list_filter = ["approved"]
    list_editable = ["approved"]
    autocomplete_fields = ["entry", "account"]


@admin.register(Event)
class EventAdmin(TranslationAdmin):
    list_display = ["title", "start", "end", "location", "public", "featured"]
    list_filter = ["public", "featured"]
    list_editable = ["public", "featured"]
    prepopulated_fields = {"slug": ["title"]}
    search_fields = ["title", "description"]
    date_hierarchy = "start"
    filter_horizontal = ["tags", "managers"]


@admin.register(EventManagementRequest)
class EventManagementRequestAdmin(admin.ModelAdmin):
    """Accessible au groupe « Administration » (core.migrations.0027) : passer
    « validée » à Oui ajoute le compte à Event.managers (EventManagementRequest.save)."""
    list_display = ["account", "event", "created", "approved"]
    list_filter = ["approved"]
    list_editable = ["approved"]
    autocomplete_fields = ["event", "account"]
