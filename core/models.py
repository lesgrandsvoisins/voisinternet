import hashlib
import hmac
import re
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

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


class Service(models.Model):
    name = models.CharField("nom", max_length=80)
    slug = models.SlugField(unique=True)
    summary = models.CharField("en une phrase", max_length=200)
    description = models.TextField(blank=True)
    retention = models.TextField(
        "ce que l'association conserve",
        blank=True,
        help_text="Ce qui reste anonyme, et ce que l'association doit conserver en tant qu'hébergeur.",
    )
    url = models.URLField("adresse du service", blank=True)
    featured = models.BooleanField("mis en avant", default=False)
    active = models.BooleanField("proposé", default=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "service"

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
        verbose_name = "compte"

    def __str__(self):
        if self.user_id:
            return f"Compte de {self.user}"
        return f"Compte anonyme n° {self.pk}"

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
    created = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["account", "service"], name="unique_shortcut")]
        verbose_name = "raccourci"

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
        ("particulier", "Particulier"),
        ("entreprise", "Entreprise"),
        ("fondation", "Fondation"),
        ("collectivite", "Collectivité"),
        ("association", "Association"),
    ]
    name = models.CharField("nom affiché", max_length=120)
    kind = models.CharField("type", max_length=20, choices=KINDS, default="particulier")
    public = models.BooleanField(
        "apparaît publiquement", default=False,
        help_text="Uniquement avec le consentement explicite du donateur (RGPD).",
    )
    since = models.DateField("soutien depuis", default=timezone.localdate)

    class Meta:
        ordering = ["-since", "name"]
        verbose_name = "donateur"

    def __str__(self):
        return self.name
