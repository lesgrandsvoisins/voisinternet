"""Évènements sur plusieurs jours : filtres « à venir » / « passés » et mise en forme des dates."""
from django.db.models import Q
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _


def a_venir(qs, maintenant=None):
    """Évènements pas encore finis : fin à venir ; sans fin, début à venir. Un évènement en cours sur plusieurs jours en fait partie."""
    maintenant = maintenant or timezone.now()
    return qs.filter(Q(end__gte=maintenant) | Q(end__isnull=True, start__gte=maintenant))


def passes(qs, maintenant=None):
    maintenant = maintenant or timezone.now()
    return qs.filter(Q(end__lt=maintenant) | Q(end__isnull=True, start__lt=maintenant))


def _local(valeur):
    return timezone.localtime(valeur) if timezone.is_aware(valeur) else valeur


def multi_jours(event):
    """Vrai si l'évènement se termine un autre jour (dans le fuseau local) que celui où il commence."""
    return bool(event.end) and _local(event.end).date() != _local(event.start).date()


def plage_texte(event):
    """Dates complètes pour la page de détail : « samedi 15 novembre 2026, 10:00 – 12:00 » ou « du jeudi 12 novembre 2026, 10:00 au samedi 14 novembre 2026, 18:00 »."""
    debut = _local(event.start)
    if not event.end:
        return date_format(debut, "l j F Y, H:i")
    fin = _local(event.end)
    if multi_jours(event):
        return _("du %(debut)s au %(fin)s") % {
            "debut": date_format(debut, "l j F Y, H:i"), "fin": date_format(fin, "l j F Y, H:i"),
        }
    return f"{date_format(debut, 'l j F Y, H:i')} – {date_format(fin, 'H:i')}"


def plage_pastille(event):
    """Pièces de la pastille de date de l'agenda : annee, semaine, jours, mois, heures (vides si sans objet)."""
    debut = _local(event.start)
    if not multi_jours(event):
        heures = date_format(debut, "H:i") + (f" – {date_format(_local(event.end), 'H:i')}" if event.end else "")
        return {"multi": False, "annee": date_format(debut, "Y"), "semaine": date_format(debut, "l"), "jours": date_format(debut, "j"),
                "mois": date_format(debut, "N"), "heures": heures}
    fin = _local(event.end)
    annee = date_format(debut, "Y") if debut.year == fin.year else f"{date_format(debut, 'Y')}–{date_format(fin, 'Y')}"
    semaine = f"{date_format(debut, 'D')} – {date_format(fin, 'D')}"
    if (debut.year, debut.month) == (fin.year, fin.month):
        return {"multi": True, "annee": annee, "semaine": semaine, "jours": f"{debut.day}–{fin.day}", "mois": date_format(debut, "N"), "heures": ""}
    return {"multi": True, "annee": annee, "semaine": semaine,
            "jours": f"{debut.day} {date_format(debut, 'N')} – {fin.day} {date_format(fin, 'N')}", "mois": "", "heures": ""}
