"""
Réglages de Voisinternet.

Tout ce qui dépend de l'installation passe par des variables d'environnement
(voir .env.example). Aucune dépendance à un service tiers : pas de CDN,
pas de police externe, pas de mesure d'audience.
"""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "oui"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)

_DEV_KEY = "dev-seulement-a-remplacer"
SECRET_KEY = env("DJANGO_SECRET_KEY", _DEV_KEY)
if SECRET_KEY == _DEV_KEY and not DEBUG:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY doit être défini en production.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# --- Connexion par le compte unique des Grands Voisins (Keycloak, OpenID Connect)
KEYCLOAK_REALM_URL = env("KEYCLOAK_REALM_URL", "").rstrip("/")
OIDC_ENABLED = bool(KEYCLOAK_REALM_URL and env("OIDC_RP_CLIENT_ID"))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]
if OIDC_ENABLED:
    INSTALLED_APPS.append("mozilla_django_oidc")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "voisinternet.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "voisinternet.wsgi.application"

# --- Base de données : SQLite par défaut (une seule sauvegarde : un fichier),
#     PostgreSQL si POSTGRES_DB est défini.
if env("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB"),
            "USER": env("POSTGRES_USER", ""),
            "PASSWORD": env("POSTGRES_PASSWORD", ""),
            "HOST": env("POSTGRES_HOST", ""),
            "PORT": env("POSTGRES_PORT", ""),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env("DJANGO_SQLITE_PATH", str(BASE_DIR / "var" / "db.sqlite3")),
        }
    }

# Cache sur disque : partagé entre les processus gunicorn, sans service en plus.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": env("DJANGO_CACHE_DIR", str(BASE_DIR / "var" / "cache")),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
if OIDC_ENABLED:
    AUTHENTICATION_BACKENDS.insert(0, "core.auth.KeycloakBackend")
    OIDC_RP_CLIENT_ID = env("OIDC_RP_CLIENT_ID")
    OIDC_RP_CLIENT_SECRET = env("OIDC_RP_CLIENT_SECRET", "")
    OIDC_RP_SIGN_ALGO = "RS256"
    OIDC_RP_SCOPES = "openid profile email"
    OIDC_OP_AUTHORIZATION_ENDPOINT = f"{KEYCLOAK_REALM_URL}/protocol/openid-connect/auth"
    OIDC_OP_TOKEN_ENDPOINT = f"{KEYCLOAK_REALM_URL}/protocol/openid-connect/token"
    OIDC_OP_USER_ENDPOINT = f"{KEYCLOAK_REALM_URL}/protocol/openid-connect/userinfo"
    OIDC_OP_JWKS_ENDPOINT = f"{KEYCLOAK_REALM_URL}/protocol/openid-connect/certs"
    OIDC_OP_LOGOUT_URL_METHOD = "core.auth.keycloak_logout_url"

LOGIN_URL = "core:je_vois"
LOGIN_REDIRECT_URL = "core:je_vois"
LOGOUT_REDIRECT_URL = "core:home"

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = env("DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Cookies : la session (compte, raccourcis) et le jeton CSRF, tous deux strictement nécessaires.
#     HTTPS et HSTS sont assurés par Caddy (voir deploy/Caddyfile).
SESSION_COOKIE_AGE = 60 * 60 * 24 * 90
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# --- Voisinternet
# Sert à calculer l'empreinte des numéros de compte anonymes.
# Ne JAMAIS la changer une fois des comptes créés : ils deviendraient introuvables.
ANON_ACCOUNT_PEPPER = env("VOISINTERNET_ANON_PEPPER", SECRET_KEY)
# Derrière Caddy ou nginx, l'adresse du visiteur arrive dans X-Forwarded-For.
BEHIND_PROXY = env_bool("VOISINTERNET_BEHIND_PROXY", False)

BLOG_URL = env("VOISINTERNET_BLOG_URL", "https://voix.voisinter.net")
GUIDE_URL = env("VOISINTERNET_GUIDE_URL", "https://voies.voisinter.net")
GHOST_URL = env("GHOST_URL", BLOG_URL)
GHOST_CONTENT_KEY = env("GHOST_CONTENT_KEY", "")
CONTACT_EMAIL = env("VOISINTERNET_CONTACT_EMAIL", "contact@voisinter.net")
