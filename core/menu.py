"""
Le plan du site est la conjugaison de « voir ».
Une seule source : l'en-tête, la page d'accueil et le pied de page lisent cette liste.
"""

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class Entry:
    key: str
    pronoun: str
    form: str
    title: str
    short: str
    detail: str
    target: str  # nom d'URL Django, ou « setting:NOM » pour une adresse externe
    group: str

    @property
    def aria(self):
        return f"{self.pronoun.capitalize()} {self.form.lower()} : {self.short}"


GROUPS = [
    ("singulier", _("au singulier, chacun")),
    ("pluriel", _("au pluriel, ensemble")),
    ("lire", _("à lire")),
]

ENTRIES = [
    Entry(
        "account",
        _("raccourcis"),
        _("& Communités"),
        _("mon Compte"),
        _("ce que vous choisissez de partager, les groupes auxquels vous adhérez"),
        _("se connecter, créer un compte, retrouver mes raccourcis"),
        "core:account",
        "singulier"
    ),
    Entry(
        "annuaire",
        _("rencontrez"),
        _("les Voisins"),
        _("Annuaire"),
        _("qui fait partie de la communauté, et comment les joindre"),
        _("un particulier, une association, une entreprise…"),
        "core:annuaire",
        "singulier",
    ),
    Entry(
        "agenda",
        _("évènements"),
        _("& Programmation"),
        _("Agenda"),
        _("les rendez-vous collectifs, en ligne ou en présence"),
        _("les conseils des voisins, deux séances pour un même ordre du jour"),
        "core:agenda",
        "singulier",
    ),
    Entry(
        "civisme",
        _("pôle"),
        _("pour se comprendre"),
        _("Civisme"),
        _("Profession d'empathie nationale, prix d'excellence en service public et en travail social"),
        _("s'engager pour l'intérêt général, entre voisins"),
        "core:civisme",
        "pluriel",
    ),
    Entry(
        "arts_plastiques",
        _("pôle"),
        _("visuel"),
        _("Arts Plastiques"),
        _("Galléries d'art dans des lieux insolites et soutien aux artistes"),
        _("transformer tout lieu en galerie d'art hybride"),
        "core:arts_plastiques",
        "pluriel",
    ),
    Entry(
        "numerique",
        _("pôle"),
        _("pour le dèsenclavement"),
        _("Numérique"),
        _("Salles de sociabilité numérique et Voisinternet"),
        _("matériel reconditionné et compétences partagées"),
        "core:numerique",
        "pluriel",
    ),
    Entry(
        "contributions",
        _("bénévolat"),
        _("& Dons"),
        _("Contributions"),
        _("du temps, un don financier, ou du matériel : sans rien attendre en retour"),
        _("donner du temps, faire un don, ou donner du matériel"),
        "core:contributions",
        "lire",
    ),
    Entry(
        "grandsvoisins",
        _("Grands"),
        _("Voisins"),
        _("L'association"),
        _("une conscience collective, l'association coopérative"),
        _("statuts, gouvernance, comptes : tout est public"),
        "core:grandsvoisins",
        "lire",
    ),
    Entry(
        "grandzine",
        _("notre blog"),
        _("GrandZine"),
        _("Lisez nos articles"),
        _("le blog couvre le civisme, les arts plastiques et le numérique"),
        _("les nouvelles et les tribunes des adhérents"),
        "setting:BLOG_URL",
        "lire",
    ),
    Entry(
        "wiki",
        _("lire"),
        _("le manuel d'utilisation"),
        _("Wiki"),
        _("le guide sur comment utiliser nos outils"),
        _("pas à pas, du premier serveur aux sauvegardes"),
        "setting:GUIDE_URL",
        "lire",
    ),
]
