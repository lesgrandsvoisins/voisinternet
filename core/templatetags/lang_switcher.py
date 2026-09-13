from django import template
from django.conf import settings
from django.utils.translation import get_language, get_language_info

register = template.Library()


@register.inclusion_tag("core/partials/lang_switcher.html", takes_context=True)
def lang_switcher(context):
    """
    Sélecteur de langue.

    Sur une page Wagtail, changer de langue via le simple préfixe d'URL
    (comme le fait `set_language`) casse dès que la traduction a un slug
    différent : /fr/a-propos/ -> /en/a-propos/ n'existe pas si la page
    anglaise s'appelle /en/about/. On construit donc des liens directs
    vers chaque traduction réellement publiée, et on n'affiche que les
    langues où une traduction existe.

    Ailleurs (pages « core »), l'URL est la même dans toutes les langues :
    on garde le mécanisme générique `set_language` (préfixe + redirection).
    """
    request = context["request"]
    current_language = get_language()
    page = context.get("page")

    if page is not None and hasattr(page, "get_translations"):
        languages = []
        for code, _name in settings.LANGUAGES:
            if code == page.locale.language_code:
                url = page.url
            else:
                translation = (
                    page.get_translations().filter(locale__language_code=code, live=True).first()
                )
                if translation is None:
                    continue
                url = translation.url
            if url is None:
                continue
            info = get_language_info(code)
            languages.append({"code": code, "name_local": info["name_local"], "url": url})
        return {"languages": languages, "current_language": current_language, "direct_links": True}

    languages = [get_language_info(code) for code, _name in settings.LANGUAGES]
    return {
        "languages": languages,
        "current_language": current_language,
        "direct_links": False,
        "next": request.get_full_path(),
    }
