from modeltranslation.translator import TranslationOptions, translator

from .models import Announcement


class AnnouncementTranslationOptions(TranslationOptions):
    fields = ("title", "text")


translator.register(Announcement, AnnouncementTranslationOptions)
