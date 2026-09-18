"""
Export/import individuel d'un évènement de l'agenda (core.Event) au format .qmd —
même principe que cms/qmd.py pour le blog, mais Event n'est pas une page Wagtail : pas
de locale/translation_key pour identifier un aller-retour. Event.source_uid (prévu à
l'origine pour dédupliquer les évènements importés d'un agenda externe comme
OpenAgenda) sert ici au même usage : généré à la première exportation s'il est vide,
puis réutilisé pour retrouver et mettre à jour le même évènement plutôt que d'en créer
un doublon.
"""
import re
import uuid

import yaml
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify

from .models import Event, Tag

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n?(.*)\Z", re.DOTALL)


def export_event_qmd(event):
    """
    Sérialise un Event en texte .qmd. Assigne un source_uid si l'évènement n'en a pas
    encore (persisté immédiatement) : sans identifiant stable, un ré-import ne saurait
    pas retrouver cet évènement et en créerait un doublon.
    """
    if not event.source_uid:
        event.source_uid = uuid.uuid4().hex
        event.save(update_fields=["source_uid"])

    front = {
        "title": event.title,
        "uid": event.source_uid,
        "slug": event.slug,
        "start": event.start.isoformat(),
    }
    if event.end:
        front["end"] = event.end.isoformat()
    if event.location:
        front["location"] = event.location
    if event.online_url:
        front["online_url"] = event.online_url
    if event.source_url:
        front["source_url"] = event.source_url
    front["public"] = event.public
    front["featured"] = event.featured
    if event.tags.exists():
        front["tags"] = list(event.tags.order_by("name").values_list("name", flat=True))

    frontmatter = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return f"---\n{frontmatter}---\n\n{event.description}\n"


def import_event_qmd(text):
    """
    Crée ou met à jour un Event à partir d'un texte .qmd. Retrouvé par son "uid"
    (Event.source_uid) quand le frontmatter en porte un — sans uid (fichier écrit à la
    main plutôt qu'exporté d'ici), un nouvel évènement est toujours créé.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("Frontmatter YAML manquant (le fichier doit commencer par ---).")
    front = yaml.safe_load(match.group(1)) or {}
    description = match.group(2).strip()

    uid = front.get("uid") or ""
    event = Event.objects.filter(source_uid=uid).first() if uid else None
    if event is None:
        event = Event(source_uid=uid)

    event.title = front.get("title") or event.title or ""
    event.slug = front.get("slug") or slugify(event.title)
    event.description = description
    start = parse_datetime(str(front["start"])) if front.get("start") else None
    if start is not None:
        event.start = start
    elif event.pk is None:
        raise ValueError("Le frontmatter doit porter une date de début (start) pour un nouvel évènement.")
    end = front.get("end")
    event.end = parse_datetime(str(end)) if end else None
    event.location = front.get("location") or ""
    event.online_url = front.get("online_url") or ""
    event.source_url = front.get("source_url") or ""
    event.public = bool(front.get("public", True))
    event.featured = bool(front.get("featured", False))
    event.save()

    tags = front.get("tags") or []
    if tags:
        event.tags.set([Tag.objects.get_or_create(name=t, defaults={"slug": slugify(t)})[0] for t in tags])

    return event
