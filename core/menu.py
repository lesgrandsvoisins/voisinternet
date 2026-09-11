"""
Le plan du site est la conjugaison de « voir ».
Une seule source : l'en-tête, la page d'accueil et le pied de page lisent cette liste.
"""
from dataclasses import dataclass


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
    ("singulier", "au singulier, chacun"),
    ("pluriel", "au pluriel, ensemble"),
    ("lire", "à lire"),
]

ENTRIES = [
    Entry("je", "je", "Vois", "Mon compte", "se connecter, mon compte, mes raccourcis",
          "se connecter, créer un compte, retrouver mes raccourcis", "core:je_vois", "singulier"),
    Entry("tu", "tu", "Vois", "Contact", "contact, se faire accompagner",
          "poser une question, se faire accompagner", "core:tu_vois", "singulier"),
    Entry("il", "il ou elle", "Voit", "Bénévolat", "bénévolat, accompagner l'autre",
          "accompagner l'autre, donner du matériel", "core:il_ou_elle_voit", "singulier"),
    Entry("nous", "nous", "Voyons", "L'association", "l'association",
          "statuts, gouvernance, comptes : tout est public", "core:nous_voyons", "pluriel"),
    Entry("vous", "vous", "Voyez", "Les services", "les services",
          "à ajouter à votre compte, même anonyme", "core:vous_voyez", "pluriel"),
    Entry("ils", "ils et elles", "Voient", "Dons et donateurs", "dons financiers et donateurs",
          "qui nous soutient, et comment nous soutenir", "core:ils_et_elles_voient", "pluriel"),
    Entry("voie", "notre", "Voie", "Le guide", "le guide",
          "pas à pas, du premier serveur aux sauvegardes", "setting:GUIDE_URL", "lire"),
    Entry("voix", "nos", "Voix", "Le blog", "le blog",
          "les nouvelles et les tribunes des adhérents", "setting:BLOG_URL", "lire"),
]
