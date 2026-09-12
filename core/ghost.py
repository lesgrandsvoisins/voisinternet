"""Derniers articles du blog Ghost (API de contenu), mis en cache."""
import json
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache
from django.utils.dateparse import parse_datetime


def _fetch_posts(cache_key, params, limit):
    posts = cache.get(cache_key)
    if posts is not None:
        return posts

    query = urlencode(params)
    request = Request(f"{settings.GHOST_URL.rstrip('/')}/ghost/api/content/posts/?{query}",
                      headers={"Accept-Version": "v5.0"})
    try:
        with urlopen(request, timeout=3) as response:
            data = json.load(response)
        posts = [
            {"title": p["title"], "url": p["url"], "published_at": parse_datetime(p["published_at"]),
             "excerpt": p.get("excerpt", "")}
            for p in data.get("posts", [])
        ]
    except (URLError, OSError, ValueError, KeyError, TypeError):
        posts = []
    # Un blog injoignable ne doit pas ralentir la page : on réessaie plus tard.
    cache.set(cache_key, posts, 900 if posts else 120)
    return posts


def latest_posts(limit=3):
    if not (settings.GHOST_URL and settings.GHOST_CONTENT_KEY):
        return []
    return _fetch_posts(
        f"ghost:latest:{limit}",
        {"key": settings.GHOST_CONTENT_KEY, "limit": limit, "fields": "title,url,published_at,excerpt"},
        limit,
    )


def posts_by_tag(tag, limit=6):
    """Derniers articles portant une étiquette Ghost donnée (civisme, arts-plastiques, numerique…)."""
    if not (settings.GHOST_URL and settings.GHOST_CONTENT_KEY):
        return []
    return _fetch_posts(
        f"ghost:tag:{tag}:{limit}",
        {"key": settings.GHOST_CONTENT_KEY, "limit": limit, "filter": f"tag:{tag}",
         "fields": "title,url,published_at,excerpt"},
        limit,
    )
