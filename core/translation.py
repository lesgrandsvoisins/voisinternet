from modeltranslation.translator import TranslationOptions, translator

from .models import Audience, GuideBook, Service


class AudienceTranslationOptions(TranslationOptions):
    fields = ("name", "who", "pitch", "note")


class ServiceTranslationOptions(TranslationOptions):
    fields = ("name", "summary", "description", "retention")


class GuideBookTranslationOptions(TranslationOptions):
    fields = ("title", "summary")


translator.register(Audience, AudienceTranslationOptions)
translator.register(Service, ServiceTranslationOptions)
translator.register(GuideBook, GuideBookTranslationOptions)
