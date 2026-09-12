from modeltranslation.translator import TranslationOptions, translator

from .models import (
    Audience, Contribution, DirectoryEntry, DirectorySector, Donor, Event, GuideBook, Service, ServiceCategory,
)


class AudienceTranslationOptions(TranslationOptions):
    fields = ("name", "who", "pitch", "note")


class ServiceCategoryTranslationOptions(TranslationOptions):
    fields = ("name",)


class ServiceTranslationOptions(TranslationOptions):
    fields = ("name", "summary", "description", "retention")


class GuideBookTranslationOptions(TranslationOptions):
    fields = ("title", "summary")


class DirectorySectorTranslationOptions(TranslationOptions):
    fields = ("name",)


class DirectoryEntryTranslationOptions(TranslationOptions):
    fields = ("name", "title", "tagline", "description", "cta_intro", "cta_label")


class EventTranslationOptions(TranslationOptions):
    fields = ("title", "description", "location")


class ContributionTranslationOptions(TranslationOptions):
    fields = ("note",)


class DonorTranslationOptions(TranslationOptions):
    fields = ("name",)


translator.register(Audience, AudienceTranslationOptions)
translator.register(ServiceCategory, ServiceCategoryTranslationOptions)
translator.register(Service, ServiceTranslationOptions)
translator.register(GuideBook, GuideBookTranslationOptions)
translator.register(DirectorySector, DirectorySectorTranslationOptions)
translator.register(DirectoryEntry, DirectoryEntryTranslationOptions)
translator.register(Event, EventTranslationOptions)
translator.register(Contribution, ContributionTranslationOptions)
translator.register(Donor, DonorTranslationOptions)
