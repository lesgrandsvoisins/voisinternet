"""
Le plan du site : une seule source, lue par l'en-tête, la page d'accueil et le pied de page.
"""

from dataclasses import dataclass

from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class Entry:
    key: str
    title: str
    short: str
    detail: str
    target: str  # nom d'URL Django, ou « setting:NOM » pour une adresse externe
    group: str

    @property
    def aria(self):
        return f"{self.title.capitalize()} : {self.short}"


def entry_href(entry):
    if entry.target.startswith("setting:"):
        return getattr(settings, entry.target.split(":", 1)[1])
    return reverse(entry.target)


GROUPS = [
    ("reperes", _("activités")),
    ("poles", _("pôles")),
    ("association", _("à propos")),
    ("compte", _("mon compte")),
]

# Pages intermédiaires (une par groupe, sauf « mon compte » qui a déjà /account/).
GROUP_PAGES = {
    "reperes": "core:activites",
    "poles": "core:poles",
    "association": "core:a_propos",
}

ENTRIES = [
    Entry(
        "raccourcis",
        _("Mes raccourcis"),
        _("les services que vous avez choisis, à ajouter ou retirer"),
        _("se connecter, créer un compte, retrouver mes raccourcis"),
        "core:raccourcis",
        "compte",
    ),
    Entry(
        "groupes",
        _("Mes groupes"),
        _("les identités auxquelles vous adhérez, individuelles ou collectives"),
        _("un particulier, une association, une entreprise…"),
        "core:groupes",
        "compte",
    ),
    Entry(
        "grandsvoisins",
        _("Association"),
        _("une conscience collective, l'association coopérative"),
        _("statuts, gouvernance, comptes : tout est public"),
        "core:grandsvoisins",
        "association",
    ),
    Entry(
        "grandzine",
        _("Blog"),
        _("le blog couvre le civisme, les arts plastiques et le numérique"),
        _("les nouvelles et les tribunes des adhérents"),
        "setting:BLOG_URL",
        "association",
    ),
    Entry(
        "contact",
        _("Contact"),
        _("une question, un problème : écrivez-nous"),
        _("un voisin vous répond, pas un robot"),
        "core:contact",
        "association",
    ),
    Entry(
        "contributions",
        _("Dons"),
        _("du temps, un don financier, ou du matériel : sans rien attendre en retour"),
        _("donner du temps, faire un don, ou donner du matériel"),
        "core:contributions",
        "association",
    ),
    Entry(
        "agenda",
        _("Agenda"),
        _("les rendez-vous collectifs, en ligne ou en présence"),
        _("les conseils des voisins, deux séances pour un même ordre du jour"),
        "core:agenda",
        "reperes",
    ),
    Entry(
        "annuaire",
        _("Annuaire"),
        _("qui fait partie de la communauté, et comment les joindre"),
        _("un particulier, une association, une entreprise…"),
        "core:annuaire",
        "reperes",
    ),
    Entry(
        "wiki",
        _("Wiki"),
        _("le guide sur comment utiliser nos outils"),
        _("pas à pas, du premier serveur aux sauvegardes"),
        "setting:GUIDE_URL",
        "reperes",
    ),
    Entry(
        "civisme",
        _("Civisme"),
        _("Profession d'empathie nationale, prix d'excellence en service public et en travail social"),
        _("s'engager pour l'intérêt général, entre voisins"),
        "core:civisme",
        "poles",
    ),
    Entry(
        "arts_plastiques",
        _("Arts Plastiques"),
        _("Galléries d'art dans des lieux insolites et soutien aux artistes"),
        _("transformer tout lieu en galerie d'art hybride"),
        "core:arts_plastiques",
        "poles",
    ),
    Entry(
        "numerique",
        _("Numérique"),
        _("Salles de sociabilité numérique et Voisinternet"),
        _("matériel reconditionné et compétences partagées"),
        "core:numerique",
        "poles",
    ),
]
