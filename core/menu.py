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
    Entry("je", _("mon Compte"), _("Compte"), _("mon Compte"), _("un individu, un compte, ce que je choisis de partager"),
          _("se connecter, créer un compte, retrouver mes raccourcis"), "core:je_vois", "singulier"),
    Entry("tu", _("Agenda"), _("programmé"), _("Agenda"), _("un individu qui reçoit de l'aide, entre voisins"),
          _("poser une question, se faire accompagner"), "core:tu_vois", "singulier"),
    Entry("il",_("Bénévolat"),_("et dons"), _("Bénévolat et dons"), _("un individu qui donne, sans rien attendre en retour"),
          _("accompagner l'autre, donner du matériel"), "core:il_ou_elle_voit", "singulier"),
    Entry("nous", _("Grands"),_("Voisins"), _("Grands Voisins"), _("une conscience collective, l'association coopérative"),
          _("statuts, gouvernance, comptes : tout est public"), "core:nous_voyons", "pluriel"),
    Entry("vous", _("Annuaire"),_("des Voisins"), _("Pages"), _("qui fait partie de la communauté, et comment les joindre"),
          _("un particulier, une association, une entreprise…"), "core:vous_voyez", "pluriel"),
    Entry("ils",  _("Pôles"), _("d'activités"), _("Pôles"), _("Civisme, arts plastique et numérique"),
          _("qui nous soutient — dons et partenaires — et comment nous soutenir"), "core:ils_et_elles_voient", "pluriel"),
    Entry("grandzine", _("blog"), _("GrandZine"), _("Blog GrandZine"), _("le blog"),
          _("les nouvelles et les tribunes des adhérents"), "setting:BLOG_URL", "lire"),
    Entry("wiki", _("Wiki"), _("/ guide"), _("Wiki / Guide"), _("le guide"),
          _("pas à pas, du premier serveur aux sauvegardes"), "setting:GUIDE_URL", "lire"),
]
