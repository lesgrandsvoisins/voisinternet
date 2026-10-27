"""Connexion par Keycloak (compte unique des Grands Voisins)."""
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import get_language
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from mozilla_django_oidc.views import OIDCAuthenticationRequestView


class KeycloakBackend(OIDCAuthenticationBackend):
    """
    Identifie les personnes par l'identifiant stable « sub » de Keycloak,
    pas par le courriel : un compte peut exister sans adresse électronique.
    """

    def filter_users_by_claims(self, claims):
        sub = claims.get("sub")
        if not sub:
            return get_user_model().objects.none()
        return get_user_model().objects.filter(username=sub)

    def create_user(self, claims):
        return get_user_model().objects.create_user(
            username=claims["sub"],
            email=claims.get("email", ""),
            first_name=claims.get("given_name", "")[:150],
            last_name=claims.get("family_name", "")[:150],
        )

    def update_user(self, user, claims):
        user.email = claims.get("email", "")
        user.first_name = claims.get("given_name", "")[:150]
        user.last_name = claims.get("family_name", "")[:150]
        user.save(update_fields=["email", "first_name", "last_name"])
        return user


def keycloak_logout_url(request):
    """Déconnexion aussi côté Keycloak, puis retour à l'accueil."""
    params = urlencode({
        "client_id": settings.OIDC_RP_CLIENT_ID,
        "post_logout_redirect_uri": request.build_absolute_uri("/"),
    })
    return f"{settings.KEYCLOAK_REALM_URL}/protocol/openid-connect/logout?{params}"


class KeycloakAuthRequestView(OIDCAuthenticationRequestView):
    """
    Départ vers Keycloak dans la langue du site (`ui_locales`, standard OIDC, et `kc_locale`,
    propre à Keycloak). Avec `register=True`, `prompt=create` ouvre directement le formulaire
    d'inscription (Keycloak ≥ 24, si l'inscription est autorisée dans le royaume).
    """

    register = False

    def get_extra_params(self, request):
        params = dict(super().get_extra_params(request))
        language = get_language() or settings.LANGUAGE_CODE
        params["ui_locales"] = language
        params["kc_locale"] = language
        if self.register:
            params["prompt"] = "create"
        return params
