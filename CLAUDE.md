# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Site for lesgrandsvoisins.com, run by Les Grands Voisins. Django 6 with
server-rendered templates and htmx (no build step, no SPA); the site works without
JavaScript — htmx only avoids full page reloads. No third-party services are loaded
(no CDN, no external fonts, no analytics).

Comments, docstrings, model verbose names and commit history in this repo are in French;
follow that convention when adding to existing files.

## Commands

Everything goes through the `Makefile` (loads `.env` automatically). See `make help`
for the full list.

```sh
make setup           # venv + install + migrate + fixtures, first-time setup
make run              # runserver on $DJANGO_IP:$DJANGO_PORT
make test             # python manage.py test core
make shell            # Django shell
make migrate          # apply migrations
make makemigrations   # generate migrations
make messages         # update .po files for en/es/ar/ko (fr is the source language)
make compilemessages  # .po -> .mo
make collectstatic
make fixtures-load    # loads core/fixtures/*.json (services, audiences, guide, sample directory data…)
make fixtures-dump    # re-dumps those same fixtures from the current DB
```

Run a single test: `.venv/bin/python manage.py test core.tests.PagesTests.test_every_page_renders`
(export `EnvironmentFile=$(pwd)/.env` first, or run via `$(LOADENV)` as the Makefile does).

There is one test module, `core/tests.py`; the `cms` app (Wagtail) has none. Tests use
`django.test.TestCase` with the `core.*` fixtures loaded via `Base.fixtures` and override
the cache to `locmem` so throttling/Ghost caching don't leak between tests.

Wagtail admin lives at `/cms/`, Django admin at `/admin/` — both are namespaced under the
active language prefix (see URLs below).

## Architecture

Two Django apps: `core` (accounts, services, directory, agenda — the app-like part of the
site) and `cms` (Wagtail page tree — the editorial/content part). `voisinternet/` is the
project package (settings, root urlconf).

### The site map is a single conjugation (`core/menu.py`)

All top-level navigation comes from one list, `ENTRIES` in `core/menu.py`, each entry
tagged with a `group` (`reperes`, `poles`, `association`, `compte`). The header, homepage
table, footer, and `core.context_processors.site` (injected into every template as `conj`
/ `conj_groups` / `header_groups`) all read this same list — add or edit a menu item there
once and every surface picks it up. An entry's `target` is either a Django URL name, a
Wagtail page via `path:/fixed/path/` (Wagtail pages have no reversible URL name — see
`entry_href`), or an external URL via `setting:SOME_SETTING`.

### Two identity systems, one `Account` (`core/accounts.py`, `core/models.py`)

- **Named**: OpenID Connect login through the Grands Voisins' Keycloak
  (`core/auth.py::KeycloakBackend`). People are matched by Keycloak's `sub` claim, not
  email — an account can exist without one.
- **Anonymous**: a 16-digit number shown once at creation; only its HMAC digest
  (`Account.number_digest`, keyed by `ANON_ACCOUNT_PEPPER`) is stored. The plaintext
  number is the sole way to recover the account on another device. Recovery attempts are
  throttled (`views._throttled`, 10 per 15 min per client IP, via `core.views._client_ip`
  which respects `X-Forwarded-For` only when `BEHIND_PROXY` is set).
- `ANON_ACCOUNT_PEPPER` (`VOISINTERNET_ANON_PEPPER`) must never change once accounts
  exist — doing so makes every anonymous account permanently unrecoverable.
- `core/accounts.py::current_account(request, create=False)` is the single entry point
  used by views/context processors to resolve "who is browsing" for both account kinds;
  it caches on `request._voisinternet_account` per request.
- A logged-in user can absorb an anonymous account left over in their session
  (`Account.absorb`, wired to `link_anonymous` view) — merges shortcuts/memberships, then
  deletes the anonymous account.
- `Service` (offered tools) and `Audience` (self-identified groups, e.g. "an association")
  attach to an `Account` through the `Shortcut` / `Membership` through-models, each with a
  personal `position` used for user-driven reordering (`reorder_shortcut`,
  `reorder_membership` views, htmx partial swaps).

### Directory ("annuaire") — self-service, consent-gated pages

`DirectoryEntry` is a public profile page (individual or collective) an account can create
and edit for itself (`mes_fiches`, `fiche_modifier` views + `DirectoryEntryForm`). Like
`Donor`, an entry is only publicly visible once `public=True` — set only by explicit
consent (GDPR), not on creation. `DirectoryEntryForm` intentionally excludes the
non-French translated fields: self-service editing only ever touches the `_fr` field of
each translated column; other languages are admin-only (modeltranslation tabs). The form
wires htmx live-preview of the Markdown description to `markdown_preview`
(`core/templatetags/markdown_filters.py`, Markdown → bleach-sanitized HTML — the only
place user-authored HTML reaches the page).

### Wagtail pages (`cms/`)

A conventional Wagtail page tree rooted at `HomePage`, with typed page models
(`StandardPage`, `PolePage`, `ContactPage`, `AssociationPage`, `DonationPage`) each
restricting their own `parent_page_types`/`subpage_types`. `PolePage` pulls in the latest
Ghost blog posts tagged with `ghost_tag` (`core/ghost.py::posts_by_tag`); `DonationPage`
pulls live `core.Service`/`core.Donor` data rather than editorial content, so those two
sections are always in sync with the admin data instead of needing manual updates.
Reusable editorial content (`CardBlock`, `BoardMemberBlock`,
`TransparencyDocumentBlock`) is shared across page types as StreamField blocks.

### Ghost blog integration (`core/ghost.py`)

Fetched via stdlib `urllib` (no HTTP client dependency) against the Ghost Content API,
cached in the file-based cache for 15 min on success / 2 min on failure — an unreachable
blog degrades to an empty list rather than breaking the homepage or a pole page.

### i18n / modeltranslation (`core/translation.py`)

Translatable model fields are registered with `django-modeltranslation`, which generates
per-language DB columns (`_fr`, `_en`, …) transparently proxied through the base field
name according to the active language. `LANGUAGES`/`MODELTRANSLATION_LANGUAGES` are
env-driven (`fr, en, es, ar, ko`); fr is the fallback. All app URLs are wrapped in
`i18n_patterns` (`voisinternet/urls.py`), so every path (including `/admin/` and `/cms/`)
is prefixed with the active language.

### Settings (`voisinternet/settings.py`)

Every environment-specific value comes from an env var (see `.env.example`), with `env()`
/ `env_bool()` / `env_list()` helpers. SQLite (`var/db.sqlite3`) is the default DB; set
`POSTGRES_DB` (and install `psycopg`, already in `requirements.txt`) to switch to
PostgreSQL. The file-based cache lives under `var/cache` — used for Ghost post caching and
request throttling, and shared across gunicorn worker processes since it's disk-based.
OIDC (Keycloak login) is entirely optional: `OIDC_ENABLED` is only true when both
`KEYCLOAK_REALM_URL` and `OIDC_RP_CLIENT_ID` are set; otherwise named login is simply
hidden, not broken.

## Deployment

`deploy/voisinternet.service` (systemd, gunicorn, 2 workers) + `deploy/Caddyfile`
(static files, HTTPS/HSTS, strict CSP, and redirects the former domains —
`voisinter.net` and the `voisinternet.fr`/`.com`/`.org` variants — to
`lesgrandsvoisins.com` keeping the path).
