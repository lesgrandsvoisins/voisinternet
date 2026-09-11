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
    Un compte Voisinternet : soit rattaché à un compte Grands Voisins (user),
    soit anonyme, retrouvable par un numéro dont seule l'empreinte est conservée.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name="voisinternet_account",
    )
    number_digest = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    services = models.ManyToManyField(Service, through="Shortcut", related_name="accounts")
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
        """Rattache les raccourcis d'un compte anonyme à ce compte, puis supprime l'anonyme."""
        for shortcut in other.shortcut_set.all():
            Shortcut.objects.get_or_create(account=self, service_id=shortcut.service_id)
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


class GuideBook(models.Model):
    """Un livre du guide (BookStack), affiché sur l'accueil."""
    title = models.CharField("titre", max_length=120)
    url = models.URLField("adresse")
    summary = models.CharField("en une phrase", max_length=200, blank=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)

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
