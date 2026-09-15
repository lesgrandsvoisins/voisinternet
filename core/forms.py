from django import forms
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from .models import DirectoryEntry

# Le formulaire d'auto-gestion n'édite que le français (champ « _fr », toujours le même
# quelle que soit la langue de navigation de la personne) : les autres langues restent
# gérables depuis l'administration (onglets de traduction). On exclut aussi le champ
# « nu » (name, title…), qui n'est qu'un alias dépendant de la langue active du site et
# ferait doublon avec son propre « _fr ».
_TRANSLATED_FIELDS = ["name", "title", "tagline", "description", "cta_intro", "cta_label"]
_OTHER_LANGUAGES = ["en", "es", "ar", "ko"]

# Regroupement des champs par onglet dans le formulaire (côté template) : purement
# présentationnel, sans effet sur la validation.
_FIELD_GROUPS = [
    (_("Général"), ["name_fr", "kind", "sector", "audiences", "title_fr", "tagline_fr", "description_fr"]),
    (_("Photos et médias"), ["logo", "photo_promo", "video_url"]),
    (_("Contact et localisation"),
     ["email", "phone", "website", "address", "city", "country", "latitude", "longitude"]),
    (_("Mise en avant"), ["cta_intro_fr", "cta_label_fr", "cta_link", "public"]),
]


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
        # Aperçu en direct du Markdown pendant la saisie (dégradation propre sans JS :
        # le champ reste un simple texte, la description s'enregistre normalement).
        self.fields["description_fr"].widget.attrs.update({
            "hx-post": reverse_lazy("core:markdown_preview"),
            "hx-trigger": "keyup changed delay:400ms, load",
            "hx-target": "#description-preview",
            "hx-swap": "innerHTML",
            "hx-params": "description_fr,csrfmiddlewaretoken",
        })

    @property
    def fieldsets(self):
        """
        Les champs du formulaire regroupés par onglet (voir _FIELD_GROUPS), avec l'onglet
        actif : le premier contenant une erreur s'il y en a, sinon le premier de la liste.
        """
        groups = [
            {"label": label, "fields": [self[name] for name in names if name in self.fields],
             "has_error": any(self[name].errors for name in names if name in self.fields)}
            for label, names in _FIELD_GROUPS
        ]
        active = next((i for i, g in enumerate(groups) if g["has_error"]), 0)
        for i, group in enumerate(groups):
            group["active"] = i == active
        return groups
