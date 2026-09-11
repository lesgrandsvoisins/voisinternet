from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from .models import Account, Audience, Donor, GuideBook, Membership, Service, ServiceCategory, Shortcut

admin.site.site_header = "Voisinternet"
admin.site.site_title = "Voisinternet"
admin.site.index_title = "Administration"


@admin.register(Audience)
class AudienceAdmin(TranslationAdmin):
    list_display = ["name", "who", "partnership", "order"]
    list_editable = ["order"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "order"]
    list_editable = ["order"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]


@admin.register(Service)
class ServiceAdmin(TranslationAdmin):
    list_display = ["name", "summary", "category", "featured", "active", "order"]
    list_filter = ["category"]
    filter_horizontal = ["audiences"]
    list_editable = ["featured", "active", "order"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name", "summary"]
    autocomplete_fields = ["category"]


class ShortcutInline(admin.TabularInline):
    model = Shortcut
    extra = 0
    autocomplete_fields = ["service"]


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["audience"]


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["__str__", "user", "created", "last_seen", "shortcut_count", "membership_count"]
    list_filter = [("user", admin.EmptyFieldListFilter)]
    readonly_fields = ["created", "last_seen"]
    inlines = [ShortcutInline, MembershipInline]

    @admin.display(description="raccourcis")
    def shortcut_count(self, obj):
        return obj.shortcut_set.count()

    @admin.display(description="appartenances")
    def membership_count(self, obj):
        return obj.membership_set.count()


@admin.register(GuideBook)
class GuideBookAdmin(TranslationAdmin):
    list_display = ["title", "url", "order"]
    list_editable = ["order"]


@admin.register(Donor)
class DonorAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "public", "since"]
    list_filter = ["kind", "public"]
    list_editable = ["public"]
