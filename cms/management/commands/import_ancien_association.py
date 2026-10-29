"""
Reprend, sous la page Association, la section « Association » de l'ancien site (old.lesgrandsvoisins.com) d'après
l'export `tools/export_ancien_site.py` (fichier contenu.jsonl) : conseils des voisins, statuts, mission, historique,
équipe, devenir membre…

    manage.py import_ancien_association /chemin/contenu.jsonl [--publier]

Pages créées en BROUILLON (relecture avant publication ; --publier pour publier), en StandardPage, avec la même
arborescence que l'ancien site. Idempotent : une page dont l'identifiant existe déjà au même endroit est laissée telle
quelle. Ce qui n'est pas repris, et est signalé à la fin : les images (l'export ne contient pas les fichiers), les
formulaires eux-mêmes (inscriptions, votes : seuls le texte et les questions posées sont repris), la page racine
« Association » (la page existe déjà ici).
"""
import json
import re
from pathlib import Path

import bleach
from django.core.management.base import BaseCommand, CommandError
from wagtail.models import Locale

from cms.models import AssociationPage, StandardPage
from core.templatetags.markdown_filters import markdown_filter

PREFIXE = "/wwwlesgrandsvoisinscom/association/"
TAGS = ["p", "br", "hr", "strong", "em", "b", "i", "s", "a", "ul", "ol", "li", "blockquote", "h2", "h3", "h4"]
ATTRS = {"a": ["href", "title"]}


def html_propre(html):
    html = re.sub(r"<(/?)h1\b", r"<\1h2", html or "")
    return bleach.clean(html, tags=TAGS, attributes=ATTRS, protocols=["http", "https", "mailto"], strip=True).strip()


def vers_html(valeur, rapport):
    """Valeur d'un bloc de l'ancien site (texte enrichi, Markdown, colonnes…) -> HTML simple."""
    if isinstance(valeur, str):
        return valeur
    if isinstance(valeur, dict):
        morceaux = []
        if valeur.get("title"):
            morceaux.append(f"<h2>{bleach.clean(valeur['title'])}</h2>")
        for cle in ("text", "body", "content"):
            if isinstance(valeur.get(cle), str):
                morceaux.append(valeur[cle])
        if valeur.get("cta_url"):
            etiquette = valeur.get("cta_label") or valeur.get("cta_text") or valeur["cta_url"]
            morceaux.append(f'<p><a href="{bleach.clean(valeur["cta_url"])}">{bleach.clean(str(etiquette))}</a></p>')
        for sous in valeur.get("columns") or []:
            morceaux.append(vers_html(sous.get("value"), rapport))
        return "".join(morceaux)
    return ""


def corps_html(contenu, rapport, url_path):
    brut = contenu.get("body") or []
    if isinstance(brut, str):
        try:
            brut = json.loads(brut)
        except ValueError:
            brut = []
    morceaux = []
    for bloc in brut:
        genre, valeur = bloc.get("type"), bloc.get("value")
        if genre == "paragraph":
            morceaux.append(valeur or "")
        elif genre == "markdown":
            morceaux.append(str(markdown_filter(valeur or "")))
        elif genre == "multicolumns":
            morceaux.append(vers_html(valeur, rapport))
        elif genre == "image":
            rapport["images"] += 1
        else:
            rapport["blocs_inconnus"].add(f"{genre} ({url_path})")
    questions = contenu.get("form_fields")
    if questions and questions != "[]":
        rapport["formulaires"] += 1
        champs = questions if isinstance(questions, list) else _lire_champs(questions)
        if champs:
            items = "".join(
                f"<li>{bleach.clean(c.get('label', ''))}"
                + (f" ({bleach.clean(', '.join(str(c['choices']).split(chr(13) + chr(10))))})" if c.get("choices") else "")
                + "</li>"
                for c in champs
            )
            morceaux.append(f"<h2>Questions posées</h2><ul>{items}</ul>")
    return html_propre("".join(morceaux))


def _lire_champs(texte):
    try:
        import ast
        return ast.literal_eval(texte)
    except (ValueError, SyntaxError):
        return []


class Command(BaseCommand):
    help = "Reprend la section Association de l'ancien site sous la page Association, en brouillon."

    def add_arguments(self, parser):
        parser.add_argument("export", help="contenu.jsonl produit par tools/export_ancien_site.py")
        parser.add_argument("--publier", action="store_true")

    def handle(self, *args, export, publier, **options):
        chemin = Path(export)
        if not chemin.is_file():
            raise CommandError(f"Fichier introuvable : {chemin}")
        racine = AssociationPage.objects.filter(locale=Locale.get_default()).first()
        if racine is None:
            raise CommandError("Page Association introuvable.")
        pages = [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]
        pages = sorted((p for p in pages if p.get("type") == "page" and p["url_path"].startswith(PREFIXE) and p["url_path"] != PREFIXE),
                       key=lambda p: p["url_path"])
        rapport = {"images": 0, "formulaires": 0, "blocs_inconnus": set()}
        creees, presentes = {}, 0
        for p in pages:
            c = p["contenu"]
            relatif = p["url_path"][len(PREFIXE):].strip("/")
            parent_chemin = relatif.rsplit("/", 1)[0] if "/" in relatif else ""
            parent = creees.get(parent_chemin) if parent_chemin else racine
            if parent is None:  # parent non repris : remonter au plus proche ancêtre repris
                parent = racine
            existante = parent.get_children().filter(slug=p["slug"]).first()
            if existante:
                creees[relatif] = existante.specific
                presentes += 1
                continue
            corps = corps_html(c, rapport, p["url_path"])
            page = StandardPage(
                title=c.get("title") or p["title"], draft_title=c.get("title") or p["title"], slug=p["slug"], live=False,
                excerpt=(c.get("search_description") or "")[:300],
                search_description=(c.get("search_description") or "")[:300],
                body=json.dumps([{"type": "prose", "value": corps}] if corps else []),
                show_in_menus=False,
            )
            parent.add_child(instance=page)
            revision = page.save_revision()
            if publier:
                revision.publish()
            creees[relatif] = page
            self.stdout.write(f"importée ({'publiée' if publier else 'brouillon'}) : association/{relatif}/")
        self.stdout.write(self.style.SUCCESS(f"{len(creees) - presentes} page(s) importée(s), {presentes} déjà présente(s)."))
        self.stdout.write(f"Non repris : {rapport['images']} image(s) (fichiers absents de l'export), "
                          f"{rapport['formulaires']} formulaire(s) (seules les questions sont reprises).")
        for inconnu in sorted(rapport["blocs_inconnus"]):
            self.stdout.write(f"Bloc non géré : {inconnu}")
