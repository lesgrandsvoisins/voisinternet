"""Recherche dans le wiki (Wiki.js, API GraphQL), mise en cache — même principe que
core/ghost.py pour le blog : dégradation propre (liste vide) si WIKIJS_API_KEY n'est
pas configurée ou si le wiki est injoignable, pour ne jamais faire échouer la page de
recherche du site à cause d'un service externe."""
import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import get_language

_SEARCH_QUERY = """
query ($query: String!, $locale: String) {
  pages {
    search(query: $query, locale: $locale) {
      results { title description path locale }
    }
  }
}
"""


def search(query, limit=10):
    """Pages du wiki correspondant à la recherche, dans la langue active."""
    if not (settings.GUIDE_URL and settings.WIKIJS_API_KEY) or not query:
        return []

    cache_key = f"wikijs:search:{get_language()}:{query}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    base_url = settings.GUIDE_URL.rstrip("/")
    payload = json.dumps({
        "query": _SEARCH_QUERY,
        "variables": {"query": query, "locale": get_language()},
    }).encode("utf-8")
    request = Request(
        f"{base_url}/graphql",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.WIKIJS_API_KEY}",
        },
    )
    try:
        with urlopen(request, timeout=3) as response:
            data = json.load(response)
        # Le paramètre locale envoyé ci-dessus n'est pas garanti d'être respecté côté
        # Wiki.js (selon le moteur de recherche configuré, ex. recherche plein texte
        # basique) : on refiltre nous-mêmes plutôt que de risquer d'afficher des
        # résultats dans une autre langue que celle demandée.
        active_locale = get_language()
        results = [
            {"title": r["title"], "description": r.get("description", ""), "url": f"{base_url}/{r['locale']}/{r['path']}"}
            for r in data["data"]["pages"]["search"]["results"]
            if r.get("locale") == active_locale
        ][:limit]
    except (URLError, OSError, ValueError, KeyError, TypeError):
        results = []
    # Un wiki injoignable ne doit pas ralentir la recherche : on réessaie plus tard.
    cache.set(cache_key, results, 300 if results else 60)
    return results
