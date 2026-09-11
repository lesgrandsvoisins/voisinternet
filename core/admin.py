from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from .models import Account, Audience, Donor, GuideBook, Service, Shortcut

admin.site.site_header = "Voisinternet"
admin.site.site_title = "Voisinternet"
admin.site.index_title = "Administration"


@admin.register(Audience)
class AudienceAdmin(TranslationAdmin):
    list_display = ["name", "who", "partnership", "order"]
    list_editable = ["order"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Service)
class ServiceAdmin(TranslationAdmin):
    list_display = ["name", "summary", "featured", "active", "order"]
    filter_horizontal = ["audiences"]
    list_editable = ["featured", "active", "order"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name", "summary"]


class ShortcutInline(admin.TabularInline):
    model = Shortcut
    extra = 0
    autocomplete_fields = ["service"]


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["__str__", "user", "created", "last_seen", "shortcut_count"]
    list_filter = [("user", admin.EmptyFieldListFilter)]
    readonly_fields = ["created", "last_seen"]
    inlines = [ShortcutInline]

    @admin.display(description="raccourcis")
    def shortcut_count(self, obj):
        return obj.shortcut_set.count()


@admin.register(GuideBook)
class GuideBookAdmin(TranslationAdmin):
    list_display = ["title", "url", "order"]
    list_editable = ["order"]


@admin.register(Donor)
class DonorAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "public", "since"]
    list_filter = ["kind", "public"]
    list_editable = ["public"]
