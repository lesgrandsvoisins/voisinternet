"""Connexion par Keycloak (compte unique des Grands Voisins)."""
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from mozilla_django_oidc.auth import OIDCAuthenticationBackend


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
