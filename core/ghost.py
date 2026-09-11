"""Derniers articles du blog Ghost (API de contenu), mis en cache."""
import json
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache
from django.utils.dateparse import parse_datetime


def latest_posts(limit=3):
    if not (settings.GHOST_URL and settings.GHOST_CONTENT_KEY):
        return []
    cache_key = f"ghost:latest:{limit}"
    posts = cache.get(cache_key)
    if posts is not None:
        return posts

    query = urlencode({"key": settings.GHOST_CONTENT_KEY, "limit": limit,
                       "fields": "title,url,published_at"})
    request = Request(f"{settings.GHOST_URL.rstrip('/')}/ghost/api/content/posts/?{query}",
                      headers={"Accept-Version": "v5.0"})
    try:
        with urlopen(request, timeout=3) as response:
            data = json.load(response)
        posts = [
            {"title": p["title"], "url": p["url"], "published_at": parse_datetime(p["published_at"])}
            for p in data.get("posts", [])
        ]
    except (URLError, OSError, ValueError, KeyError, TypeError):
        posts = []
    # Un blog injoignable ne doit pas ralentir l'accueil : on réessaie plus tard.
    cache.set(cache_key, posts, 900 if posts else 120)
    return posts
