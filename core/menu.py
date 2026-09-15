"""
Le plan du site : une seule source, lue par l'en-tête, la page d'accueil et le pied de page.
"""

from dataclasses import dataclass

from django.conf import settings
from django.urls import reverse
from django.utils.translation import get_language, gettext_lazy as _


@dataclass(frozen=True)
class Entry:
    key: str
    title: str
    short: str
    detail: str
    target: str  # nom d'URL Django, « setting:NOM » ou « path:/chemin/ » (page Wagtail à URL fixe)
    group: str
    htmltarget: str

    @property
    def aria(self):
        return f"{self.title.capitalize()} : {self.short}"


def entry_href(entry):
    if entry.target.startswith("setting:"):
        return getattr(settings, entry.target.split(":", 1)[1])
    if entry.target.startswith("path:"):
        # Pages Wagtail : pas de nom d'URL Django à inverser, juste le
        # chemin (fixe, indépendant de la langue) préfixé par la langue
        # active — comme le ferait i18n_patterns pour une URL nommée.
        return f"/{get_language()}{entry.target.split(':', 1)[1]}"
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
        "_self",
    ),
    Entry(
        "groupes",
        _("Mes groupes"),
        _("les identités auxquelles vous adhérez, individuelles ou collectives"),
        _("un particulier, une association, une entreprise…"),
        "core:groupes",
        "compte",
        "_self",
    ),
    Entry(
        "grandsvoisins",
        _("Association"),
        _("une conscience collective, l'association coopérative"),
        _("statuts, gouvernance, comptes : tout est public"),
        "path:/grandsvoisins/",
        "association",
        "_self",
    ),
    Entry(
        "grandzine",
        _("Blog"),
        _("le blog couvre le civisme, les arts plastiques et le numérique"),
        _("les nouvelles et les tribunes des adhérents"),
        "setting:BLOG_URL",
        "association",
        "_new",
    ),
    Entry(
        "contact",
        _("Contact"),
        _("une question, un problème : écrivez-nous"),
        _("un voisin vous répond, pas un robot"),
        "path:/contact/",
        "association",
        "_self",
    ),
    Entry(
        "contributions",
        _("Dons"),
        _("du temps, un don financier, ou du matériel : sans rien attendre en retour"),
        _("donner du temps, faire un don — à titre personnel ou associatif — ou donner du matériel"),
        "path:/contributions/",
        "association",
        "_self",
    ),
    Entry(
        "agenda",
        _("Agenda"),
        _("les rendez-vous collectifs, en ligne ou en présence"),
        _("les conseils des voisins, deux séances pour un même ordre du jour"),
        "core:agenda",
        "reperes",
        "_self",
    ),
    Entry(
        "annuaire",
        _("Annuaire"),
        _("qui fait partie de la communauté, et comment les joindre"),
        _("un particulier, une association, une entreprise…"),
        "core:annuaire",
        "reperes",
        "_self",
    ),
    Entry(
        "wiki",
        _("Wiki"),
        _("le guide sur comment utiliser nos outils"),
        _("pas à pas, du premier serveur aux sauvegardes"),
        "setting:GUIDE_URL",
        "reperes",
        "_new",
    ),
    Entry(
        "civisme",
        _("Civisme"),
        _("Profession d'empathie nationale, prix d'excellence en service public et en travail social"),
        _("s'engager pour l'intérêt général, entre voisins et associations"),
        "path:/civisme/",
        "poles",
        "_self",
    ),
    Entry(
        "arts_plastiques",
        _("Arts Plastiques"),
        _("Galléries d'art dans des lieux insolites et soutien aux artistes"),
        _("transformer tout lieu en galerie d'art hybride"),
        "path:/arts-plastiques/",
        "poles",
        "_self",
    ),
    Entry(
        "numerique",
        _("Numérique"),
        _("Salles de sociabilité numérique et lesgrandsvoisins.com"),
        _("matériel reconditionné et compétences partagées, pour les particuliers comme pour les associations"),
        "path:/numerique/",
        "poles",
        "_self",
    ),
]
