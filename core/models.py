import hashlib
import hmac
import re
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

ANON_DIGITS = 16


def normalize_number(raw):
    """Garde les chiffres : « 1234 5678-9012 3456 » devient « 1234567890123456 »."""
    digits = re.sub(r"\D", "", raw or "")
    return digits if len(digits) == ANON_DIGITS else None


def format_number(digits):
    return " ".join(digits[i:i + 4] for i in range(0, len(digits), 4))


def number_digest(digits):
    key = settings.ANON_ACCOUNT_PEPPER.encode()
    return hmac.new(key, digits.encode(), hashlib.sha256).hexdigest()


class Audience(models.Model):
    """
    À qui s'adresse-t-on. Des mots de tous les jours, pas des catégories juridiques :
    le statut (personne physique ou morale) se précise au moment du compte ou du contrat.
    """
    name = models.CharField(_("vous êtes…"), max_length=80, help_text=_("Par exemple : « Une association »."))
    slug = models.SlugField(unique=True)
    who = models.CharField(_("qui est concerné"), max_length=200, blank=True)
    pitch = models.CharField(_("en une phrase"), max_length=240)
    note = models.TextField(_("texte de la page"), blank=True)
    partnership = models.BooleanField(
        _("partenariat plutôt que services"), default=False,
        help_text=_("Pour les acteurs publics et sociaux : la page propose un partenariat, sans bouton « Ajouter »."),
    )
    order = models.PositiveSmallIntegerField(_("ordre"), default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = _("public")
        verbose_name_plural = _("publics")

    def __str__(self):
        return self.name


class ServiceCategory(models.Model):
    """Regroupement des services par nature (compte, communication, fichiers…), à la manière de www.gv.je."""
    name = models.CharField(_("nom"), max_length=80)
    slug = models.SlugField(unique=True)
    order = models.PositiveSmallIntegerField(_("ordre"), default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = _("catégorie de service")
        verbose_name_plural = _("catégories de service")

    def __str__(self):
        return self.name


class Service(models.Model):
    name = models.CharField(_("nom"), max_length=80)
    slug = models.SlugField(unique=True)
    summary = models.CharField(_("en une phrase"), max_length=200)
    description = models.TextField(blank=True)
    retention = models.TextField(
        _("ce que l'association conserve"),
        blank=True,
        help_text=_("Ce qui reste anonyme, et ce que l'association doit conserver en tant qu'hébergeur."),
    )
    url = models.URLField(_("adresse du service"), blank=True)
    icon = models.ImageField(_("icône"), upload_to="services/icones/", blank=True)
    category = models.ForeignKey(
        ServiceCategory, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="services", verbose_name=_("catégorie"),
    )
    audiences = models.ManyToManyField(
        Audience, blank=True, related_name="services", verbose_name=_("publics"),
        help_text=_("Laisser vide si le service s'adresse à tout le monde."),
    )
    featured = models.BooleanField(_("mis en avant"), default=False)
    active = models.BooleanField(_("proposé"), default=True)
    order = models.PositiveSmallIntegerField(_("ordre"), default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = _("service")

    def __str__(self):
        return self.name


class Account(models.Model):
    """
    Un compte lesgrandsvoisins.com : soit rattaché à un compte Grands Voisins (user),
    soit anonyme, retrouvable par un numéro dont seule l'empreinte est conservée.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name="voisinternet_account",
    )
    number_digest = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    services = models.ManyToManyField(Service, through="Shortcut", related_name="accounts")
    groups = models.ManyToManyField(Audience, through="Membership", related_name="accounts")
    created = models.DateTimeField(default=timezone.now, editable=False)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("compte")

    def __str__(self):
        if self.user_id:
            return _("Compte de %(user)s") % {"user": self.user}
        return _("Compte anonyme n° %(pk)s") % {"pk": self.pk}

    @property
    def is_anonymous_only(self):
        return self.user_id is None

    @classmethod
    def create_anonymous(cls):
        """Crée un compte anonyme et renvoie (compte, numéro en clair). Le numéro n'est jamais stocké."""
        while True:
            digits = "".join(str(secrets.randbelow(10)) for _ in range(ANON_DIGITS))
            digest = number_digest(digits)
            if not cls.objects.filter(number_digest=digest).exists():
                return cls.objects.create(number_digest=digest), digits

    @classmethod
    def find_by_number(cls, raw):
        digits = normalize_number(raw)
        if not digits:
            return None
        return cls.objects.filter(number_digest=number_digest(digits), user__isnull=True).first()

    def absorb(self, other):
        """Rattache les raccourcis et appartenances d'un compte anonyme à ce compte, puis supprime l'anonyme."""
        for shortcut in other.shortcut_set.all():
            Shortcut.objects.get_or_create(account=self, service_id=shortcut.service_id)
        for membership in other.membership_set.all():
            Membership.objects.get_or_create(account=self, audience_id=membership.audience_id)
        other.delete()


class Shortcut(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    position = models.PositiveIntegerField(_("ordre personnel"), default=0)
    created = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["account", "service"], name="unique_shortcut")]
        ordering = ["account", "position", "service__name"]
        verbose_name = _("raccourci")

    def __str__(self):
        return f"{self.service} ({self.account})"


class Membership(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    audience = models.ForeignKey(Audience, on_delete=models.CASCADE)
    position = models.PositiveIntegerField(_("ordre personnel"), default=0)
    created = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["account", "audience"], name="unique_membership")]
        ordering = ["account", "position", "audience__name"]
        verbose_name = _("appartenance")

    def __str__(self):
        return f"{self.audience} ({self.account})"


class DirectorySector(models.Model):
    """Secteur d'activité de l'annuaire (civisme, arts plastiques…), à la manière de gdvoisins.com."""
    name = models.CharField(_("nom"), max_length=80)
    slug = models.SlugField(unique=True)
    order = models.PositiveSmallIntegerField(_("ordre"), default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = _("secteur d'activité")
        verbose_name_plural = _("secteurs d'activité")

    def __str__(self):
        return self.name


class DirectoryEntry(models.Model):
    """
    Une page de l'annuaire (« vous Voyez ») : une personne ou une structure de la communauté.
    Comme pour les donateurs, la page n'apparaît publiquement qu'avec le consentement explicite
    de la personne ou de la structure concernée.
    """
    KINDS = [
        ("individuel", _("Individuel")),
        ("collectif", _("Collectif")),
    ]
    name = models.CharField(_("nom"), max_length=120)
    slug = models.SlugField(unique=True, max_length=120)
    kind = models.CharField(_("individuel ou collectif"), max_length=20, choices=KINDS, default="individuel")
    sector = models.ForeignKey(
        DirectorySector, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="entries", verbose_name=_("secteur"),
    )
    audiences = models.ManyToManyField(
        Audience, blank=True, related_name="directory_entries", verbose_name=_("publics"),
        help_text=_("Laisser vide si la fiche s'adresse à tout le monde."),
    )

    owner = models.ForeignKey(
        Account, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="directory_entries", verbose_name=_("compte propriétaire"),
    )
    title = models.CharField(_("titre de la page"), max_length=140, blank=True, default="")
    tagline = models.CharField(_("texte d'accroche"), max_length=240, blank=True, default="")
    description = models.TextField(_("description"), blank=True, default="")

    logo = models.ImageField(_("logo"), upload_to="annuaire/logos/", blank=True, default="")
    photo_promo = models.ImageField(_("photo promotionnelle"), upload_to="annuaire/photos/", blank=True, default="")
    video_url = models.URLField(
        _("vidéo promotionnelle"), blank=True, default="",
        help_text=_("Lien vers une vidéo (YouTube, PeerTube…) : affiché en lien, jamais intégré en cadre."),
    )

    email = models.EmailField(_("courriel"), blank=True, default="")
    phone = models.CharField(_("téléphone"), max_length=30, blank=True, default="")
    website = models.URLField(_("site ou lien"), blank=True, default="")

    address = models.CharField(_("adresse"), max_length=200, blank=True, default="")
    city = models.CharField(_("ville"), max_length=100, blank=True, default="")
    country = models.CharField(_("pays"), max_length=100, blank=True, default="")
    latitude = models.DecimalField(_("latitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(_("longitude"), max_digits=9, decimal_places=6, null=True, blank=True)

    cta_intro = models.CharField(_("introduction de l'appel à l'action"), max_length=200, blank=True, default="")
    cta_label = models.CharField(_("texte du bouton d'appel à l'action"), max_length=60, blank=True, default="")
    cta_link = models.URLField(_("lien de l'appel à l'action"), blank=True, default="")

    public = models.BooleanField(
        _("apparaît publiquement"), default=False,
        help_text=_("Uniquement avec le consentement explicite de la personne ou de la structure (RGPD)."),
    )
    order = models.PositiveSmallIntegerField(_("ordre"), default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = _("page de l'annuaire")
        verbose_name_plural = _("pages de l'annuaire")

    def __str__(self):
        return self.name

    @property
    def photos(self):
        gallery = [p.image for p in self.gallery_photos.all()]
        return ([self.photo_promo] if self.photo_promo else []) + gallery


class DirectoryEntryPhoto(models.Model):
    """
    Une photo supplémentaire d'une fiche de l'annuaire (galerie), en plus de la photo
    promotionnelle : une fiche peut en avoir un nombre quelconque, avec une légende.
    """
    entry = models.ForeignKey(DirectoryEntry, on_delete=models.CASCADE, related_name="gallery_photos")
    image = models.ImageField(_("photo"), upload_to="annuaire/photos/")
    caption = models.CharField(_("légende"), max_length=200, blank=True, default="")
    order = models.PositiveSmallIntegerField(_("ordre"), default=0)

    class Meta:
        ordering = ["order", "pk"]
        verbose_name = _("photo de l'annuaire")
        verbose_name_plural = _("photos de l'annuaire")

    def __str__(self):
        return self.caption or f"Photo de {self.entry}"


class EntrySubscription(models.Model):
    """Un compte qui suit la fiche d'une autre personne ou structure dans l'annuaire."""
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    entry = models.ForeignKey(DirectoryEntry, on_delete=models.CASCADE, related_name="subscriptions")
    created = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["account", "entry"], name="unique_entry_subscription")]
        ordering = ["account", "entry__name"]
        verbose_name = _("abonnement à une fiche")
        verbose_name_plural = _("abonnements aux fiches")

    def __str__(self):
        return f"{self.entry} ({self.account})"


class Event(models.Model):
    """
    Un évènement de l'agenda (conseil des voisins, atelier…).

    Une même rencontre importée d'une source externe (OpenAgenda…) peut avoir
    plusieurs séances (même ordre du jour, horaires différents) : ce sont
    alors plusieurs Event partageant le même source_uid.
    """
    title = models.CharField(_("titre"), max_length=140)
    # Pas unique : plusieurs séances d'un même évènement source partagent le même titre.
    slug = models.SlugField(_("slug"))
    description = models.TextField(_("description"), blank=True, default="")
    start = models.DateTimeField(_("début"))
    end = models.DateTimeField(_("fin"), null=True, blank=True)
    location = models.CharField(_("lieu"), max_length=200, blank=True, default="")
    photo = models.ImageField(_("photo"), upload_to="agenda/photos/", blank=True, default="")
    latitude = models.DecimalField(_("latitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(_("longitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    online_url = models.URLField(
        _("lien en ligne"), blank=True, default="",
        help_text=_("Pour une participation à distance (visioconférence…)."),
    )
    source_url = models.URLField(
        _("lien source"), blank=True, default="",
        help_text=_("Page de l'évènement sur l'agenda source (OpenAgenda…)."),
    )
    source_uid = models.CharField(
        _("identifiant source"), max_length=64, blank=True, default="",
        help_text=_("Identifiant de l'évènement dans l'agenda source, pour réimporter sans dupliquer."),
    )
    public = models.BooleanField(_("publié"), default=True)

    class Meta:
        ordering = ["start"]
        verbose_name = _("évènement")
        verbose_name_plural = _("évènements")

    def __str__(self):
        return self.title


class Contribution(models.Model):
    """Une contribution financière enregistrée pour un compte (adhésion, don ponctuel…)."""
    METHODS = [
        ("helloasso", "HelloAsso"),
        ("paypal", "PayPal"),
        ("stripe", "Stripe"),
        ("autre", _("Autre")),
    ]
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="contributions")
    amount = models.DecimalField(_("montant"), max_digits=8, decimal_places=2)
    method = models.CharField(_("moyen"), max_length=20, choices=METHODS, default="helloasso")
    date = models.DateField(_("date"), default=timezone.localdate)
    note = models.CharField(_("note"), max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-date"]
        verbose_name = _("contribution financière")
        verbose_name_plural = _("contributions financières")

    def __str__(self):
        return f"{self.amount} € ({self.account})"


class GuideBook(models.Model):
    """Un livre du guide (BookStack), affiché sur l'accueil."""
    title = models.CharField("titre", max_length=120)
    url = models.URLField("adresse")
    summary = models.CharField("en une phrase", max_length=200, blank=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)
    published = models.BooleanField("publié", default=True)

    class Meta:
        ordering = ["order", "title"]
        verbose_name = "livre du guide"
        verbose_name_plural = "livres du guide"

    def __str__(self):
        return self.title


class Donor(models.Model):
    KINDS = [
        ("particulier", _("Particulier")),
        ("entreprise", _("Entreprise")),
        ("fondation", _("Fondation")),
        ("collectivite", _("Collectivité")),
        ("association", _("Association")),
    ]
    name = models.CharField(_("nom affiché"), max_length=120)
    kind = models.CharField(_("type"), max_length=20, choices=KINDS, default="particulier")
    public = models.BooleanField(
        _("apparaît publiquement"), default=False,
        help_text=_("Uniquement avec le consentement explicite du donateur (RGPD)."),
    )
    since = models.DateField(_("soutien depuis"), default=timezone.localdate)

    class Meta:
        ordering = ["-since", "name"]
        verbose_name = _("donateur")

    def __str__(self):
        return self.name
