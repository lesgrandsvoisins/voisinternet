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
    # par une espace. Coupe naïvement par caractère : largement suffisant ici (titres et
    # descriptions courtes), pas besoin de gérer les limites d'octets UTF-8 au caractère près.
    if len(line.encode("utf-8")) <= 75:
        return line
    parts = []
    while len(line.encode("utf-8")) > 75:
        parts.append(line[:74])
        line = " " + line[74:]
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
