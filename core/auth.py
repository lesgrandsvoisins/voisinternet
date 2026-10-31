"""Connexion par Keycloak (compte unique des Grands Voisins)."""
import base64
import json
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from mozilla_django_oidc.views import OIDCAuthenticationRequestView


def _adresses(claims):
    """Adresses de la boîte lues dans le claim « lgvmail » (une chaîne ou une liste) ; rien d'inventé si le claim manque."""
    adresses = claims.get("lgvmail") or []
    if isinstance(adresses, str):
        adresses = [adresses]
    return [a for a in adresses if isinstance(a, str) and "@" in a]


LOGIN_IDENTIFIER_KEY = "voisinternet_login_identifier"
MAIL_ADDRESSES_KEY = "voisinternet_mail_addresses"


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

    def get_userinfo(self, access_token, id_token, payload):
        """
        Garde en session l'identifiant de connexion Keycloak (« preferred_username », calculé à l'inscription : jusqu'à
        5 lettres du nom + 5 du prénom, un numéro seulement s'il est déjà pris) et les adresses de la boîte (claim
        multivalué « lgvmail » : domaine principal et domaines supplémentaires, réglés côté serveur, jamais écrits ici),
        pour les montrer à la personne. Les claims sont lus dans `userinfo` d'abord, puis dans le jeton d'identité : selon
        la configuration du mapper Keycloak (« Add to userinfo » / « Add to ID token »), l'un ou l'autre peut manquer.
        """
        claims = dict(super().get_userinfo(access_token, id_token, payload))
        if isinstance(payload, (bytes, str)):
            try:
                payload = json.loads(payload)
            except ValueError:
                payload = {}
        payload = payload if isinstance(payload, dict) else {}
        for name in ("preferred_username", "lgvmail"):
            if not claims.get(name) and payload.get(name):
                claims[name] = payload[name]   # create_user() lit ces claims : même source des deux côtés
        username = claims.get("preferred_username", "")
        request = getattr(self, "request", None)
        if request is not None and username:
            request.session[LOGIN_IDENTIFIER_KEY] = username
        adresses = _adresses(claims)
        if request is not None:
            if adresses:
                request.session[MAIL_ADDRESSES_KEY] = adresses
            else:
                request.session.pop(MAIL_ADDRESSES_KEY, None)
        return claims

    def create_user(self, claims):
        request = getattr(self, "request", None)
        if request is not None and claims.get("preferred_username"):
            messages.success(request, _(
                "Bienvenue ! Votre identifiant de connexion est %(identifier)s : notez-le, "
                "il ne change pas."
            ) % {"identifier": claims["preferred_username"]})
            adresses = _adresses(claims)
            if adresses:
                messages.success(request, _(
                    "Vos adresses de courriel (une seule boîte) : %(addresses)s."
                ) % {"addresses": ", ".join(adresses)})
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


def _end_session_endpoint():
    """Adresse de déconnexion de Keycloak : `end_session_endpoint` de la découverte OIDC du royaume (mise en cache), sinon
    l'adresse standard du royaume — la même source que les adresses d'autorisation et de jeton du réglage."""
    defaut = f"{settings.KEYCLOAK_REALM_URL}/protocol/openid-connect/logout"
    cle = f"oidc-end-session-endpoint:{settings.KEYCLOAK_REALM_URL}"  # par royaume : un changement de nom ne sert pas l'ancien
    trouve = cache.get(cle)
    if trouve:
        return trouve
    try:
        with urlopen(f"{settings.KEYCLOAK_REALM_URL}/.well-known/openid-configuration", timeout=3) as reponse:
            trouve = json.loads(reponse.read().decode("utf-8")).get("end_session_endpoint") or defaut
        cache.set(cle, trouve, 3600)
    except (OSError, ValueError):
        trouve = defaut
        cache.set(cle, trouve, 300)  # injoignable : on réessaie dans 5 minutes, sans retarder chaque déconnexion
    return trouve


def _emetteur(id_token):
    """Émetteur (`iss`) annoncé par un id_token, lu SANS vérification (il ne sert qu'à choisir le paramètre de déconnexion)."""
    try:
        charge = id_token.split(".")[1]
        charge += "=" * (-len(charge) % 4)
        return str(json.loads(base64.urlsafe_b64decode(charge)).get("iss", "")).rstrip("/")
    except (IndexError, ValueError, TypeError):
        return ""


def keycloak_logout_url(request):
    """
    Adresse où envoyer le navigateur après avoir effacé la session locale : déconnexion à l'initiative de l'application
    (OpenID Connect « RP-initiated logout »). Avec l'id_token gardé à la connexion (`id_token_hint`), Keycloak déconnecte
    sans page de confirmation ; sans lui (session ancienne), repli sur `client_id`. L'id_token n'est ni journalisé ni
    montré au navigateur ailleurs que dans cette adresse de redirection, à l'adresse de Keycloak.
    Réglage VOISINTERNET_DECONNEXION_KEYCLOAK=non : retour à l'accueil sans toucher à la session Keycloak.
    """
    accueil = request.build_absolute_uri(reverse("core:home"))
    if not settings.DECONNEXION_KEYCLOAK:
        return accueil
    params = {"post_logout_redirect_uri": accueil}
    id_token = request.session.get("oidc_id_token")
    if id_token and _emetteur(id_token) not in ("", settings.KEYCLOAK_REALM_URL):
        id_token = None  # jeton délivré sous un ancien nom du royaume (changement de domaine) : repli sur client_id
    if id_token:
        params["id_token_hint"] = id_token
    else:
        params["client_id"] = settings.OIDC_RP_CLIENT_ID
    return f"{_end_session_endpoint()}?{urlencode(params)}"


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
