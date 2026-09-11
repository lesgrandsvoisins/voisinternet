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

# Le pronom et la forme conjuguée (« je » / « Vois »…) restent en français dans toutes
# les langues : c'est la signature du site, comme son nom. Seuls le titre, l'accroche
# courte et le détail sont traduits.
ENTRIES = [
    Entry("je", "je", "Vois", _("Mon compte"), _("se connecter, mon compte, mes raccourcis"),
          _("se connecter, créer un compte, retrouver mes raccourcis"), "core:je_vois", "singulier"),
    Entry("tu", "tu", "Vois", _("Contact"), _("contact, se faire accompagner"),
          _("poser une question, se faire accompagner"), "core:tu_vois", "singulier"),
    Entry("il", "il ou elle", "Voit", _("Bénévolat"), _("bénévolat, accompagner l'autre"),
          _("accompagner l'autre, donner du matériel"), "core:il_ou_elle_voit", "singulier"),
    Entry("nous", "nous", "Voyons", _("Association"), _("l'association"),
          _("statuts, gouvernance, comptes : tout est public"), "core:nous_voyons", "pluriel"),
    Entry("vous", "vous", "Voyez", _("Services"), _("les services"),
          _("à ajouter à votre compte, même anonyme"), "core:vous_voyez", "pluriel"),
    Entry("ils", "ils et elles", "Voient", _("Dons et donateurs"), _("dons financiers et donateurs"),
          _("qui nous soutient, et comment nous soutenir"), "core:ils_et_elles_voient", "pluriel"),
    Entry("voix", "nos", "Voix", _("Blog"), _("le blog"),
          _("les nouvelles et les tribunes des adhérents"), "setting:BLOG_URL", "lire"),
    Entry("voie", "notre", "Voie", _("Guide"), _("le guide"),
          _("pas à pas, du premier serveur aux sauvegardes"), "setting:GUIDE_URL", "lire"),
]
