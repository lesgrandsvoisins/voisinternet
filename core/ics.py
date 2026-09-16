"""Génère un fichier .ics (RFC 5545) minimal pour un évènement de l'agenda."""
from datetime import timezone as dt_timezone

from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags

from .templatetags.markdown_filters import markdown_filter


def _escape(value):
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line):
    # RFC 5545 : une ligne de plus de 75 octets doit être repliée, la suite démarrant
    # par une espace. Découpe caractère par caractère (pas d'octet coupé en deux) en
    # s'arrêtant dès que la part atteint 75 octets, pour rester valide avec des accents.
    if len(line.encode("utf-8")) <= 75:
        return line
    parts = []
    while len(line.encode("utf-8")) > 75:
        cut = 74
        while len(line[:cut].encode("utf-8")) > 75:
            cut -= 1
        parts.append(line[:cut])
        line = " " + line[cut:]
    parts.append(line)
    return "\r\n".join(parts)


def _dt(value):
    return value.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def event_to_ics(event, request):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//lesgrandsvoisins.com//Agenda//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:event-{event.pk}@lesgrandsvoisins.com",
        f"DTSTAMP:{_dt(timezone.now())}",
        f"DTSTART:{_dt(event.start)}",
    ]
    if event.end:
        lines.append(f"DTEND:{_dt(event.end)}")
    lines.append(_fold(f"SUMMARY:{_escape(event.title)}"))
    if event.description:
        plain = strip_tags(markdown_filter(event.description)).strip()
        lines.append(_fold(f"DESCRIPTION:{_escape(plain)}"))
    location = event.location or event.online_url
    if location:
        lines.append(_fold(f"LOCATION:{_escape(location)}"))
    url = event.online_url or event.source_url or request.build_absolute_uri(
        reverse("core:event_detail", args=[event.pk]),
    )
    lines.append(f"URL:{url}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


def event_google_calendar_url(event):
    """
    Lien "Ajouter à Google Agenda" (calendar.google.com/render) : contrairement au
    fichier .ics ci-dessus, Google Agenda ne propose pas d'ouvrir/importer un .ics
    en un clic, donc ce lien direct est le seul moyen simple d'y ajouter l'évènement.
    """
    from urllib.parse import urlencode

    params = {
        "action": "TEMPLATE",
        "text": event.title,
        "dates": f"{_dt(event.start)}/{_dt(event.end or event.start)}",
    }
    location = event.location or event.online_url
    if location:
        params["location"] = location
    if event.description:
        params["details"] = strip_tags(markdown_filter(event.description)).strip()
    return "https://calendar.google.com/calendar/render?" + urlencode(params)
