"""Correspondance entre les adresses de l'ancien site (old.lesgrandsvoisins.com) ou du blog Ghost et celles d'ici.

Partagé par la redirection des anciennes adresses (`core.views.ancien_site`) et par la réécriture des liens du contenu
(`manage.py reecrire_liens`)."""
from django.utils.text import slugify

# Rubriques du vieux site (old.lesgrandsvoisins.com, adresses /fr-fr/<rubrique>/…) -> adresse équivalente ici.
OLD_SITE_SECTIONS = {
    "association": "/grandsvoisins/",
    "activités": "/activites/",
    "activites": "/activites/",
    "civisme": "/civisme/",
    "numerique": "/numerique/",
    "contact": "/contact/",
    "agenda": "/agenda/",
    "annuaire": "/annuaire/",
    "blog": "/blog/",
}


# Billets de blog dont l'adresse a changé à la reprise (même titre, autre identifiant) : ancien -> nouveau.
OLD_BLOG_RENAMED = {
    "17e-conseil-des-voisins": "17e-conseil",
    "18e-conseil-des-voisins": "18e-conseil",
    "20e-conseil-des-voisins": "20e-conseil-des-voisins-lun-18-dec-paris-14e-et-visio",
    "a-propos-de-lesgrandsvoisinscom": "a-propos-de-lesgrandsvoisins-com",
    "essai-video-entretien-handicap-france-soudan-darfour-international": "essai-video-entretien",
    "inclusivday-au-cnit-10-mai": "nous-a-inclusivday-cnit-10-mai-2023",
    "interet-general": "notre-qualite-dinteret-general",
    "la-marque-les-grands-voisins-est-une-responsabilite-pour-nimporte-qui": "la-marque-est-une-responsabilite-pour-nimporte-qui",
    "lettre-ouverte-son-excellence-mohamed-ould-cheikh-ghazouani": "lettre-ouverte-a-son-excellence-monsieur-mohamed-ould-cheikh-ghazouani-president-de-la-republique-islamique-de-mauritanie",
    "manifeste-des-grands-voisins": "manifeste-2023",
    "nom-les-grands-voisins": "les-grands-voisins-par-un-autre-nom-est-toujours-lesgrandsvoisins-com",
    "obtention-du-statut-cooperative": "coop-2023",
    "point-davancements-en-mars-2022": "points-avancement-mars-2022",
    "point-sur-les-avancements-en-mai-2022": "avancements-mai-2022",
    "qui-est-expert-etou-legitime": "qui-est-expert-et-ou-legitime",
    "retour-sur-ghostio-comme-techno-de-site-web": "revenu-sur-ghost-io",
    "sites-faciles": "refonte-web-avec-sites-faciles",
    "thoughts-about-creative-commons-cc-by-nc-sa-en": "baldart-article",
}


def equivalent_blog(slug):
    """Adresse ici d'un billet de l'ancien blog (Ghost ou vieux site), ou None s'il n'existe pas (publié)."""
    from cms.models import BlogPostPage

    slug = slugify(slug)
    post = BlogPostPage.objects.live().filter(slug=OLD_BLOG_RENAMED.get(slug, slug)).first()
    return post.url if post else None


def equivalent_ancien_site(parts, exact=False):
    """Adresse ici d'une page du vieux site (`parts` : segments après /fr-fr/ ou /fr/).

    exact=False : à défaut de page équivalente, la rubrique correspondante (redirection) ; None si la rubrique est
    inconnue. exact=True : seulement une vraie page équivalente (sinon None) — pour réécrire un lien sans le vider de
    son sens."""
    from core.models import DirectoryEntry, Event

    if not parts:
        return "/fr/"
    section, leaf = parts[0].lower(), parts[1] if len(parts) > 1 else ""
    base = OLD_SITE_SECTIONS.get(section)
    if base is None:
        return None
    if len(parts) == 2:
        slug = slugify(leaf)
        if section == "annuaire" and DirectoryEntry.objects.filter(slug=slug).exists():
            return f"/fr/annuaire/{slug}/"
        if section == "blog":
            url = equivalent_blog(slug)
            if url:
                return url
        if section == "agenda":
            for event in Event.objects.filter(public=True):
                titre = slugify(event.title_fr or event.title)
                if titre and (titre == slug or titre.startswith(slug) or slug.startswith(titre)):
                    return f"/fr/agenda/{event.pk}/"
    if exact:
        return f"/fr{base}" if len(parts) == 1 else None
    return f"/fr{base}"
