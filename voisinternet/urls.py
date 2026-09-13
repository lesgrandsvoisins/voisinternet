from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("documents/", include(wagtaildocs_urls)),
]

if settings.OIDC_ENABLED:
    urlpatterns.append(path("oidc/", include("mozilla_django_oidc.urls")))

urlpatterns += i18n_patterns(
    path("admin/", admin.site.urls),
    path("cms/", include(wagtailadmin_urls)),
    path("", include("core.urls")),
    path("", include(wagtail_urls)),
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
