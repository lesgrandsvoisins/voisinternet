from django import forms
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Contribution, DirectoryEntry, Event

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
    (_("Général"), ["name_fr", "description_fr", "website"]),
    (_("Photos et médias"), ["logo", "photo_promo", "video_url"]),
    (_("Présentation"), ["layout"]),
    (_("Publication"), ["visibility"]),
    (_("Catégories"), ["kind", "sector", "tags", "audiences", "title_fr", "tagline_fr"]),
    (_("Mise en avant"), ["cta_intro_fr", "cta_label_fr", "cta_link"]),
    (_("Contact"), ["email", "phone"]),
    (_("Adresse"), ["country", "region", "city", "postal_code", "address"]),
    (_("Avancé"), ["latitude", "longitude"]),
]


class DirectoryEntryForm(forms.ModelForm):
    class Meta:
        model = DirectoryEntry
        # "approved" (validation du groupe « Administration ») n'est jamais éditable ici :
        # sinon la personne pourrait se publier elle-même sans validation.
        exclude = ["owner", "slug", "order", "approved"] + _TRANSLATED_FIELDS + [
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
        self.fields["tagline_fr"].label = _("Description courte")
        # Aperçu en direct du Markdown pendant la saisie (dégradation propre sans JS :
        # le champ reste un simple texte, la description s'enregistre normalement).
        self.fields["description_fr"].widget.attrs.update({
            "hx-post": reverse_lazy("core:markdown_preview"),
            "hx-trigger": "keyup changed delay:400ms, load",
            "hx-target": "#description-preview",
            "hx-swap": "innerHTML",
            "hx-params": "description_fr,csrfmiddlewaretoken",
            # Accroche l'éditeur enrichi (site.js) : dégradation propre sans JS, le champ
            # reste alors un simple texte Markdown/HTML.
            "data-wysiwyg": "1",
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


_EVENT_TRANSLATED_FIELDS = ["title", "description", "location"]
_EVENT_LANGUAGES = ["fr", "en", "es", "ar", "ko"]


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        # "public"/"featured" ne sont jamais éditables ici : un évènement créé en
        # self-service reste réservé à ses responsables tant que le groupe
        # « Administration » (core:administration) ne l'a pas publié. "managers" non plus
        # (ajouté via le parcours de demande, pas ici — voir claim_event_management).
        # Contrairement à DirectoryEntryForm (toujours _fr, quelle que soit la langue de
        # navigation) : seuls les champs "nus" (title/description/location) sont exclus
        # ici, pas les variantes par langue — __init__ ne garde que celle de la langue
        # active, pour créer/modifier un évènement dans la langue qu'on est en train de
        # parcourir plutôt que toujours en français.
        exclude = ["slug", "public", "featured", "managers", "source_url", "source_uid"] + _EVENT_TRANSLATED_FIELDS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.utils.translation import get_language

        lang = get_language() if get_language() in _EVENT_LANGUAGES else "fr"
        for field in _EVENT_TRANSLATED_FIELDS:
            for other_lang in _EVENT_LANGUAGES:
                lang_field = f"{field}_{other_lang}"
                if lang_field not in self.fields:
                    continue
                if other_lang == lang:
                    self.fields[lang_field].label = self.fields[lang_field].label.replace(f" [{lang}]", "")
                else:
                    del self.fields[lang_field]
        self.fields[f"title_{lang}"].required = True


class ContributionForm(forms.Form):
    """
    Auto-déclaration d'une contribution (voir views.faire_don) : une promesse et son
    paiement restent deux enregistrements indépendants (voir Contribution), donc « les
    deux » crée les deux à la fois plutôt qu'un seul enregistrement ambigu.
    """
    KIND_PLEDGE = Contribution.PLEDGE
    KIND_PAYMENT = Contribution.PAYMENT
    KIND_BOTH = "both"
    KIND_CHOICES = [
        (KIND_PLEDGE, _("Une promesse de don")),
        (KIND_PAYMENT, _("Un paiement déjà effectué")),
        (KIND_BOTH, _("Une promesse, réglée dans le même temps")),
    ]
    kind = forms.ChoiceField(
        label=_("Type"), choices=KIND_CHOICES, widget=forms.RadioSelect, initial=KIND_PLEDGE,
    )
    amount = forms.DecimalField(label=_("Montant"), min_value=0.01, max_digits=8, decimal_places=2)
    method = forms.ChoiceField(label=_("Moyen"), choices=Contribution.METHODS, initial="virement")
    date = forms.DateField(
        label=_("Date"), initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}),
    )
    note = forms.CharField(label=_("Note"), max_length=200, required=False)


class ContactMessageForm(forms.Form):
    """
    Formulaire de contact générique — un·e auteur·ice de blog (views.author_detail,
    cms.AuthorMessage) ou une fiche de l'annuaire (views.entry_detail,
    core.models.EntryMessage) : le message part par e-mail à l'adresse de la cible,
    une copie est conservée pour modération/traçabilité. "website" est un piège à
    robots (honeypot) : un champ masqué qu'une personne ne remplit jamais, mais qu'un
    robot générique remplit souvent — la vue traite un champ non vide comme un envoi
    silencieusement ignoré.
    """
    sender_name = forms.CharField(label=_("Votre nom"), max_length=140, required=False)
    sender_email = forms.EmailField(label=_("Votre e-mail"))
    message = forms.CharField(label=_("Message"), max_length=4000, widget=forms.Textarea)
    website = forms.CharField(required=False, widget=forms.HiddenInput)
