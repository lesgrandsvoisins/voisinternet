from django.contrib import admin
from modeltranslation.admin import TranslationAdmin, TranslationTabularInline

from .models import (
    Account, Audience, Contribution, DirectoryEntry, DirectoryEntryPhoto, DirectorySector, Donor, EntrySubscription,
    Event, GuideBook,
    Membership, Service, ServiceCategory, Shortcut,
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


@admin.register(Service)
class ServiceAdmin(TranslationAdmin):
    list_display = ["name", "summary", "category", "featured", "active", "requires_approval", "order"]
    list_filter = ["category", "requires_approval"]
    filter_horizontal = ["audiences"]
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
    filter_horizontal = ["audiences"]
    inlines = [DirectoryEntryPhotoInline]
    fieldsets = [
        (None, {
            "fields": ["name", "slug", "kind", "sector", "audiences", "owner", "visibility", "approved", "order"],
        }),
        ("Présentation", {"fields": ["title", "tagline", "description"]}),
        ("Médias", {"fields": ["logo", "photo_promo", "video_url"]}),
        ("Coordonnées", {"fields": ["email", "phone", "website"]}),
        ("Localisation", {"fields": ["address", "postal_code", "city", "region", "country", "latitude", "longitude"]}),
        ("Appel à l'action", {"fields": ["cta_intro", "cta_label", "cta_link"]}),
    ]


@admin.register(EntrySubscription)
class EntrySubscriptionAdmin(admin.ModelAdmin):
    list_display = ["account", "entry", "created"]
    autocomplete_fields = ["entry"]


@admin.register(Event)
class EventAdmin(TranslationAdmin):
    list_display = ["title", "start", "end", "location", "public"]
    list_filter = ["public"]
    list_editable = ["public"]
    prepopulated_fields = {"slug": ["title"]}
    search_fields = ["title", "description"]
    date_hierarchy = "start"
