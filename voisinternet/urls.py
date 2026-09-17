from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

urlpatterns = [
    path("documents/", include(wagtaildocs_urls)),
]

if settings.OIDC_ENABLED:
    urlpatterns.append(path("oidc/", include("mozilla_django_oidc.urls")))

urlpatterns += i18n_patterns(
    # À l'intérieur de i18n_patterns (pas hors, comme le suggère la doc Django) : sinon
    # /i18n/setlang/ n'a lui-même aucun préfixe, donc LocaleMiddleware active pour CETTE
    # requête la langue du cookie/Accept-Language/LANGUAGE_CODE plutôt que celle de la
    # page d'où vient le changement — si elle ne correspond pas au préfixe de "next",
    # django.urls.translate_url() (utilisé par la vue set_language) échoue silencieusement
    # à résoudre l'URL sous ce préfixe (Resolver404, intercepté) et renvoie l'URL de départ
    # inchangée : le sélecteur de langue change la langue (cookie posé) mais ne navigue
    # jamais vers l'URL traduite.
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("cms/", include(wagtailadmin_urls)),
    path("", include("core.urls")),
    path("", include(wagtail_urls)),
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
