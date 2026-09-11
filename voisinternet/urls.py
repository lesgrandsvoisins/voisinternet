from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
]

if settings.OIDC_ENABLED:
    urlpatterns.insert(1, path("oidc/", include("mozilla_django_oidc.urls")))
