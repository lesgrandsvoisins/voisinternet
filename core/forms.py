from django import forms

from .models import DirectoryEntry

# Le formulaire d'auto-gestion n'édite que le français (champ « _fr », toujours le même
# quelle que soit la langue de navigation de la personne) : les autres langues restent
# gérables depuis l'administration (onglets de traduction). On exclut aussi le champ
# « nu » (name, title…), qui n'est qu'un alias dépendant de la langue active du site et
# ferait doublon avec son propre « _fr ».
_TRANSLATED_FIELDS = ["name", "title", "tagline", "description", "cta_intro", "cta_label"]
_OTHER_LANGUAGES = ["en", "es", "ar", "ko"]


class DirectoryEntryForm(forms.ModelForm):
    class Meta:
        model = DirectoryEntry
        exclude = ["owner", "slug", "order"] + _TRANSLATED_FIELDS + [
            f"{field}_{lang}" for field in _TRANSLATED_FIELDS for lang in _OTHER_LANGUAGES
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in _TRANSLATED_FIELDS:
            fr_field = f"{field}_fr"
            if fr_field in self.fields:
                self.fields[fr_field].label = self.fields[fr_field].label.replace(" [fr]", "")
        # modeltranslation rend tous les champs par langue non-obligatoires en base : on
        # réimpose ici que le nom (en français) reste requis pour créer une fiche.
        self.fields["name_fr"].required = True
