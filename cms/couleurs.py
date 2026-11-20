"""Couleurs d'un site Wagtail individuel : validation (forme #RRGGBB et contraste lisible) et calcul d'une variante de survol."""
import re

TEXTE_SOMBRE = "#1C2A35"  # couleur du texte du site (--ink) et des boutons « soleil » (.btn-sun)
RE_COULEUR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _rvb(couleur):
    return tuple(int(couleur[i:i + 2], 16) for i in (1, 3, 5))


def luminance(couleur):
    def canal(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(v) for v in _rvb(couleur))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a, b):
    """Rapport de contraste WCAG entre deux couleurs #RRGGBB (4,5 : seuil du texte courant)."""
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def assombrir(couleur, part=0.06):
    return "#" + "".join(f"{int(v * (1 - part)):02X}" for v in _rvb(couleur))


def erreur_couleur(couleur, sur_texte=TEXTE_SOMBRE):
    """Message d'erreur (en français) si la couleur est mal écrite ou si le texte sombre n'y est pas lisible ; sinon chaîne vide."""
    if not couleur:
        return ""
    if not RE_COULEUR.match(couleur):
        return "Écrivez la couleur sous la forme #RRGGBB (par exemple #E8F1E4)."
    rapport = contraste(couleur, sur_texte)
    if rapport < 4.5:
        return f"Cette couleur est trop sombre : le texte n'y serait pas lisible (contraste {rapport:.1f}, il en faut au moins 4,5). Choisissez une couleur plus claire."
    return ""
