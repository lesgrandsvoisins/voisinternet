import json
import re
from unittest import mock
from urllib.error import URLError

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone, translation

from cms.models import Author, AuthorMessage, ContentPage, PolePage
from cms.qmd import export_contentpage_qmd, import_contentpage_qmd

from .accounts import SESSION_KEY
from .forms import ContactMessageForm
from .models import (
    Account, Audience, Contribution, DirectoryEntry, DirectorySector, Donor, EntryMessage, EntrySubscription,
    Event, EventInterest, EventManagementRequest, Membership, OwnershipClaim, Service, Shortcut, Tag, format_number,
)


# Les tests historiques supposent la création implicite d'un compte anonyme (réglage « ouvert ») ; le comportement par
# défaut, « discret », est couvert par AnonymeDiscretTests.
@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    ANONYMOUS_ACCOUNTS="ouvert",
)
class Base(TestCase):
    fixtures = ["core.audience.json", "core.guidebook.json", "core.servicecategory.json", "core.service.json"]

    def setUp(self):
        cache.clear()
        self.service = Service.objects.get(slug="roundcube-webmail")


class PagesTests(Base):
    def test_every_page_renders(self):
        # Un raccourci crée un compte : nécessaire pour que « raccourcis » et « groupes » répondent 200.
        self.client.post(reverse("core:toggle_shortcut", args=[self.service.slug]))
        for name in ["home", "account", "raccourcis", "groupes", "agenda",
                     "annuaire", "activites", "poles", "a_propos"]:
            with self.subTest(page=name):
                response = self.client.get(reverse(f"core:{name}"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="main-menu-panel"')  # le menu principal est présent

    def test_footer_language_switcher(self):
        # Sélecteur de langue du pied de page : une entrée par langue, sans JavaScript.
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, 'class="foot-lang"')
        for code in ["fr", "en", "es", "ar", "ko"]:
            self.assertContains(response, f'name="language" value="{code}"')

    def test_wagtail_pages_render(self):
        # Pages gérées par Wagtail (cms.PolePage, ContactPage, AssociationPage,
        # DonationPage) : pas de nom d'URL Django à inverser (voir core/menu.py).
        for path in ["/fr/civisme/", "/fr/arts-plastiques/", "/fr/numerique/",
                     "/fr/contact/", "/fr/grandsvoisins/", "/fr/contributions/"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="main-menu-panel"')

    @override_settings(OIDC_ENABLED=True, KEYCLOAK_REALM_URL="https://key.example/realms/gv",
                       OIDC_RP_CLIENT_ID="voisinternet")
    def test_header_offers_register_and_login_for_new_visitor(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, reverse("core:inscription"))
        self.assertContains(response, reverse("core:connexion"))

    def test_header_widget_lists_shortcuts_once_an_account_exists(self):
        # Une fois un compte créé (même anonyme), le widget bascule des actions de
        # connexion vers la liste des raccourcis et l'action de fermeture du compte.
        self.client.post(reverse("core:toggle_shortcut", args=[self.service.slug]))
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, self.service.name)
        self.assertContains(response, "Fermer ce compte sur cet appareil")

    def test_current_page_is_marked(self):
        response = self.client.get(reverse("core:annuaire"))
        self.assertContains(response, 'aria-current="page"')

    def test_group_page_lists_its_entries(self):
        response = self.client.get(reverse("core:activites"))
        self.assertContains(response, "Annuaire")
        self.assertContains(response, "Agenda")
        self.assertContains(response, "Wiki")

    def test_header_menu_is_a_flat_list_without_account_group(self):
        # Le menu de l'en-tête est une liste plate (pas d'onglets, pas de lien vers les
        # pages intermédiaires) et n'affiche pas « mon compte » : ce groupe vit dans le widget.
        response = self.client.get(reverse("core:home"))
        content = response.content.decode()
        panel = content[content.index('id="main-menu-panel"'):content.index("</nav>", content.index('id="main-menu-panel"'))]
        self.assertIn(reverse("core:agenda"), panel)
        self.assertIn(reverse("core:annuaire"), panel)
        self.assertIn('class="menu-sep"', panel)
        self.assertNotIn(reverse("core:activites"), panel)
        self.assertNotIn("Mes liens", panel)


class ContentPageQmdTests(Base):
    def setUp(self):
        super().setUp()
        self.pole = PolePage.objects.get(slug="civisme")

    def test_pole_lists_published_content_pages_as_cards(self):
        page = ContentPage(
            title="Astuces numériques", slug="astuces-numeriques", live=True,
            excerpt="Un chapeau de carte.", body=[{"type": "prose", "value": "<p>Bonjour.</p>"}],
        )
        self.pole.add_child(instance=page)

        response = self.client.get(self.pole.url)
        self.assertContains(response, "Astuces numériques")
        self.assertContains(response, "Un chapeau de carte.")
        self.assertContains(response, 'class="pole-card')

    def test_content_page_renders_prose_and_callout(self):
        page = ContentPage(
            title="Page de contenu", slug="page-de-contenu", live=True,
            body=[
                {"type": "prose", "value": "<p>Texte normal.</p>"},
                {
                    "type": "callout",
                    "value": {"type": "tip", "title": "Astuce", "text": "<p>Contenu du callout.</p>"},
                },
            ],
        )
        self.pole.add_child(instance=page)

        response = self.client.get(page.url)
        self.assertContains(response, "Texte normal.")
        self.assertContains(response, 'class="callout callout-tip"')
        self.assertContains(response, "Astuce")
        self.assertContains(response, "Contenu du callout.")

    def test_content_page_paginates_on_pagebreak(self):
        page = ContentPage(
            title="Page paginée", slug="page-paginee", live=True,
            body=[
                {"type": "prose", "value": '<p>Début.</p><hr class="pagebreak"><p>Suite.</p>'},
                {"type": "callout", "value": {"type": "note", "title": "", "text": "<p>Un callout.</p>"}},
            ],
        )
        self.pole.add_child(instance=page)

        response = self.client.get(page.url)
        # Les deux pages sont présentes dans le HTML (pour l'impression complète, comme
        # BlogPostPage), seule la 2e est masquée à l'écran via l'attribut "hidden".
        divs = re.findall(r'<div class="markdown"( hidden)?>(.*?)</div>', response.content.decode(), re.S)
        self.assertEqual(len(divs), 2)
        self.assertEqual(divs[0][0], "")
        self.assertIn("Début.", divs[0][1])
        self.assertEqual(divs[1][0], " hidden")
        self.assertIn("Suite.", divs[1][1])
        self.assertIn("Un callout.", divs[1][1])  # le callout reste entier sur la 2e page, jamais scindé
        self.assertContains(response, "Page 1 sur 2")

        response = self.client.get(page.url, {"page": 2})
        divs = re.findall(r'<div class="markdown"( hidden)?>(.*?)</div>', response.content.decode(), re.S)
        self.assertEqual(divs[0][0], " hidden")
        self.assertEqual(divs[1][0], "")
        self.assertContains(response, "Page 2 sur 2")

    def test_content_page_toc_covers_current_page_only(self):
        page = ContentPage(
            title="Page à sommaire", slug="page-a-sommaire", live=True,
            body=[
                {
                    "type": "prose",
                    "value": (
                        '<h2>Introduction</h2><p>Texte.</p>'
                        '<h2>Introduction</h2>'  # doublon volontaire -> ancre dédupliquée
                        '<hr class="pagebreak">'
                        '<h2>Conclusion</h2>'
                    ),
                },
            ],
        )
        self.pole.add_child(instance=page)

        response = self.client.get(page.url)
        content = response.content.decode()
        self.assertIn('id="introduction"', content)
        self.assertIn('id="introduction-1"', content)  # dédoublonnage
        toc_nav = re.search(r'<nav class="content-toc[^"]*".*?</nav>', content, re.S)
        self.assertIsNotNone(toc_nav)
        self.assertIn('href="#introduction"', toc_nav.group())
        self.assertNotIn("Conclusion", toc_nav.group())  # sur l'autre page, hors sommaire

        response = self.client.get(page.url, {"page": 2})
        content = response.content.decode()
        # Une seule entrée sur la 2e page -> pas de sommaire affiché (toc|length > 1).
        self.assertNotIn('class="content-toc', content)

    def test_content_page_shows_related_content(self):
        tag, _ = Tag.objects.get_or_create(slug="test-contenu-lie", defaults={"name": "Test contenu lié"})
        page = ContentPage(title="Page A", slug="page-a", live=True, body=[])
        self.pole.add_child(instance=page)
        page.tags.set([tag])
        other = ContentPage(title="Page B", slug="page-b", live=True, body=[])
        self.pole.add_child(instance=other)
        other.tags.set([tag])

        response = self.client.get(page.url)
        self.assertContains(response, "À lire aussi")
        self.assertContains(response, "Page B")

    def test_content_page_related_excludes_other_locales(self):
        # Bug réel observé en production : sans filtre de langue, une traduction du
        # même article (une Page distincte, même étiquette) se faisait passer pour un
        # contenu lié différent — voir ContentPage.get_context et BlogPostPage.get_context.
        from wagtail.models import Locale

        tag, _ = Tag.objects.get_or_create(slug="test-locale-tag", defaults={"name": "Test locale"})
        page = ContentPage(title="Page FR", slug="page-fr-locale", live=True, body=[])
        self.pole.add_child(instance=page)
        page.tags.set([tag])

        translated = page.copy_for_translation(Locale.objects.get(language_code="en"), copy_parents=True)
        translated.tags.set([tag])
        translated.save_revision().publish()

        response = self.client.get(page.url)
        self.assertNotContains(response, "À lire aussi")

    def test_pull_quote_div_and_span_round_trip(self):
        qmd_text = """---
title: Page avec citation
key: 66666666-6666-6666-6666-666666666666
lang: fr
pole: civisme
slug: page-avec-citation
---

Un texte avec une citation glissée en ligne : [Voici une citation.]{.pull} La suite du paragraphe.

::: {.pull}
Une citation plus longue,

sur plusieurs paragraphes.
:::

Fin du texte.
"""
        page = import_contentpage_qmd(qmd_text)
        blocks = list(page.body)
        self.assertEqual([b.block_type for b in blocks], ["prose", "pull", "prose"])
        self.assertIn('<span class="pull">Voici une citation.</span>', str(blocks[0].value))
        self.assertIn("Une citation plus longue", str(blocks[1].value["text"]))
        self.assertIn("sur plusieurs paragraphes", str(blocks[1].value["text"]))

        response = self.client.get(page.url)
        self.assertContains(response, 'class="pull"')

        exported = export_contentpage_qmd(page)
        self.assertIn("[Voici une citation.]{.pull}", exported)
        self.assertIn("::: {.pull}", exported)
        self.assertIn("Une citation plus longue", exported)

        reimported = import_contentpage_qmd(exported)
        self.assertEqual(reimported.pk, page.pk)
        reimported_blocks = list(reimported.body)
        self.assertEqual([b.block_type for b in blocks], [b.block_type for b in reimported_blocks])

    def test_qmd_round_trip_is_isomorphic(self):
        # Callout multi-paragraphes, tableau, et note de bas de page dont la définition
        # est séparée de sa référence — la convention Quarto/Pandoc habituelle.
        qmd_text = """---
title: Page de test qmd
key: 11111111-1111-1111-1111-111111111111
lang: fr
pole: civisme
slug: page-test-qmd
---

Texte d'introduction avec une note de bas de page[^1].

| Colonne 1 | Colonne 2 |
| --- | --- |
| a | b |

::: {.callout-note title="Astuce"}
Premier paragraphe du callout.

Second paragraphe du callout, avec **du gras**.
:::

Texte de conclusion.

[^1]: Contenu de la note.
"""
        page = import_contentpage_qmd(qmd_text)
        blocks = list(page.body)
        # Un seul bloc "prose" avant le callout : texte d'intro et tableau ne sont
        # séparés par aucun callout, donc restent un seul bloc continu.
        self.assertEqual([b.block_type for b in blocks], ["prose", "callout", "prose"])
        # Table et note de bas de page survivent dans ce premier bloc "prose".
        self.assertIn("<table>", str(blocks[0].value))
        self.assertIn("Colonne 1", str(blocks[0].value))
        self.assertIn("footnote", str(blocks[0].value))
        # Callout multi-paragraphes préservé comme un seul bloc, pas éclaté.
        self.assertEqual(blocks[1].value["type"], "note")
        self.assertEqual(blocks[1].value["title"], "Astuce")
        self.assertIn("Premier paragraphe", str(blocks[1].value["text"]))
        self.assertIn("Second paragraphe", str(blocks[1].value["text"]))

        exported = export_contentpage_qmd(page)
        self.assertIn('::: {.callout-note title="Astuce"}', exported)
        self.assertIn("| Colonne 1 | Colonne 2 |", exported)
        self.assertIn("[^1]: Contenu de la note.", exported)

        reimported = import_contentpage_qmd(exported)
        self.assertEqual(reimported.pk, page.pk)  # même clé de traduction -> mise à jour, pas doublon
        reimported_blocks = list(reimported.body)
        self.assertEqual([b.block_type for b in blocks], [b.block_type for b in reimported_blocks])
        self.assertEqual(reimported_blocks[1].value["title"], "Astuce")
        self.assertIn("Second paragraphe", str(reimported_blocks[1].value["text"]))

    def test_generic_nested_div_round_trip(self):
        # Exemple de la documentation Pandoc/Quarto elle-même (divs imbriqués) :
        # https://quarto.org/docs/authoring/markdown-basics.html#sec-divs-and-spans —
        # une classe non reconnue (.sidebar) imbriquant elle-même un autre div (.warning)
        # et de la prose ("Plus de contenu.") doit survivre à l'aller-retour sans rien
        # perdre, alors qu'aucun des deux n'a d'équivalent Wagtail dédié (contrairement
        # à .callout-*/.pull) — voir cms.models.GenericBlock/GenericNestingBlock.
        qmd_text = """---
title: Page avec divs imbriqués
key: 77777777-7777-7777-7777-777777777777
lang: fr
pole: civisme
slug: page-divs-imbriques
---

:::: {.sidebar}

::: {.warning}
Attention à ceci.
:::

Plus de contenu.

::::

Fin du texte.
"""
        page = import_contentpage_qmd(qmd_text)
        blocks = list(page.body)
        self.assertEqual([b.block_type for b in blocks], ["generic_nesting", "prose"])
        self.assertEqual(blocks[0].value["class_name"], ".sidebar")
        nested = list(blocks[0].value["children"])
        self.assertEqual([b.block_type for b in nested], ["generic", "prose"])
        self.assertEqual(nested[0].value["class_name"], ".warning")
        self.assertIn("Attention à ceci", str(nested[0].value["text"]))
        self.assertIn("Plus de contenu", str(nested[1].value))

        response = self.client.get(page.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attention à ceci")
        self.assertContains(response, "Plus de contenu")

        exported = export_contentpage_qmd(page)
        self.assertIn(":::: {.sidebar}", exported)
        self.assertIn("::: {.warning}", exported)
        self.assertIn("Attention à ceci", exported)
        self.assertIn("Plus de contenu", exported)

        reimported = import_contentpage_qmd(exported)
        self.assertEqual(reimported.pk, page.pk)
        reimported_blocks = list(reimported.body)
        self.assertEqual([b.block_type for b in blocks], [b.block_type for b in reimported_blocks])
        reimported_nested = list(reimported_blocks[0].value["children"])
        self.assertEqual([b.block_type for b in nested], [b.block_type for b in reimported_nested])
        self.assertIn("Attention à ceci", str(reimported_nested[0].value["text"]))


class AnonymousAccountTests(Base):
    def test_adding_a_service_creates_an_anonymous_account(self):
        response = self.client.post(reverse("core:toggle_shortcut", args=[self.service.slug]))
        self.assertRedirects(response, reverse("core:raccourcis"), fetch_redirect_response=False)
        account = Account.objects.get()
        self.assertTrue(account.is_anonymous_only)
        self.assertTrue(Shortcut.objects.filter(account=account, service=self.service).exists())
        # Le numéro reste affiché, sur toutes les pages, jusqu'à confirmation explicite.
        for _ in range(2):
            page = self.client.get(reverse("core:home"))
            self.assertContains(page, "Votre numéro de compte anonyme")
            # Les chiffres se lisent toujours de gauche à droite, même dans une langue RTL (arabe).
            self.assertContains(page, 'id="number-banner-code" dir="ltr"')
        download = self.client.get(reverse("core:download_number"))
        self.assertEqual(download.status_code, 200)
        self.assertIn("attachment", download["Content-Disposition"])
        self.client.post(reverse("core:confirm_number"))
        self.assertNotContains(self.client.get(reverse("core:home")), "Votre numéro de compte anonyme")
        self.assertEqual(self.client.get(reverse("core:download_number")).status_code, 404)

    def test_first_steps_are_ticked_from_data(self):
        self.client.post(reverse("core:toggle_shortcut", args=[self.service.slug]))
        page = self.client.get(reverse("core:account"))
        self.assertContains(page, "Premiers pas")
        self.assertContains(page, "1 sur")

    def test_login_identifier_is_shown_in_profile(self):
        user = get_user_model().objects.create_user("sub-123", first_name="Jean")
        self.client.force_login(user)
        session = self.client.session
        session["voisinternet_login_identifier"] = "dupojean2@gv.je"
        session.save()
        self.assertContains(self.client.get(reverse("core:account")), "dupojean2@gv.je")

    def test_mail_addresses_are_read_from_the_account_never_written_in_code(self):
        user = get_user_model().objects.create_user("sub-456", first_name="Lucie")
        self.client.force_login(user)
        page = self.client.get(reverse("core:account"))
        self.assertNotContains(page, "Adresses de courriel")           # sans claim : rien d'affiché, aucun domaine inventé
        session = self.client.session
        session["voisinternet_mail_addresses"] = ["duponlucie@exemple.test", "duponlucie@autre.test"]
        session.save()
        page = self.client.get(reverse("core:account"))
        self.assertContains(page, "duponlucie@exemple.test, duponlucie@autre.test")
        # Visible d'emblée en haut de « Mon compte » (et non seulement dans la rubrique « Mon profil », repliée).
        haut = page.content.decode().split('id="sc2-title"')[0]
        self.assertIn("duponlucie@exemple.test, duponlucie@autre.test", haut)

    @override_settings(OIDC_ENABLED=True, OIDC_RP_CLIENT_ID="voisinternet", OIDC_RP_CLIENT_SECRET="x",
                       OIDC_OP_AUTHORIZATION_ENDPOINT="https://key.example/auth", OIDC_OP_TOKEN_ENDPOINT="https://key.example/token",
                       OIDC_OP_USER_ENDPOINT="https://key.example/user", OIDC_OP_JWKS_ENDPOINT="https://key.example/certs")
    def test_userinfo_keeps_identifier_and_all_mail_addresses_from_claims(self):
        from django.test import RequestFactory
        from core.auth import KeycloakBackend

        request = RequestFactory().get("/")
        request.session = self.client.session
        backend = KeycloakBackend()
        backend.request = request
        claims = {"sub": "s1", "preferred_username": "duponlucie@a.test", "lgvmail": ["duponlucie@a.test", "duponlucie@b.test"]}
        with mock.patch("mozilla_django_oidc.auth.OIDCAuthenticationBackend.get_userinfo", return_value=claims):
            backend.get_userinfo("t", "i", {})
        self.assertEqual(request.session["voisinternet_login_identifier"], "duponlucie@a.test")
        self.assertEqual(request.session["voisinternet_mail_addresses"], ["duponlucie@a.test", "duponlucie@b.test"])
        # Mapper Keycloak seulement dans le JETON D'IDENTITÉ (pas dans userinfo) : lu quand même.
        request.session.pop("voisinternet_mail_addresses", None)
        request.session.pop("voisinternet_login_identifier", None)
        with mock.patch("mozilla_django_oidc.auth.OIDCAuthenticationBackend.get_userinfo", return_value={"sub": "s1"}):
            retour = backend.get_userinfo("t", "i", {"preferred_username": "x@a.test", "lgvmail": ["x@a.test", "x@b.test"]})
        self.assertEqual(request.session["voisinternet_mail_addresses"], ["x@a.test", "x@b.test"])
        self.assertEqual(request.session["voisinternet_login_identifier"], "x@a.test")
        self.assertEqual(retour["lgvmail"], ["x@a.test", "x@b.test"])   # create_user() verra le même claim
        # Un claim absent efface les adresses d'une connexion précédente (pas d'adresse périmée affichée).
        with mock.patch("mozilla_django_oidc.auth.OIDCAuthenticationBackend.get_userinfo", return_value={"sub": "s1"}):
            backend.get_userinfo("t", "i", {})
        self.assertNotIn("voisinternet_mail_addresses", request.session)

    def test_connexion_is_404_without_oidc(self):
        with override_settings(OIDC_ENABLED=False):
            self.assertEqual(self.client.get(reverse("core:inscription")).status_code, 404)

    @override_settings(OIDC_ENABLED=True, KEYCLOAK_REALM_URL="https://key.example/realms/gv",
                       OIDC_RP_CLIENT_ID="voisinternet",
                       OIDC_OP_AUTHORIZATION_ENDPOINT="https://key.example/auth",
                       OIDC_OP_TOKEN_ENDPOINT="https://key.example/token",
                       OIDC_OP_USER_ENDPOINT="https://key.example/user",
                       OIDC_RP_CLIENT_SECRET="x")
    def test_inscription_passes_language_and_create_prompt(self):
        self.addCleanup(translation.activate, "fr")  # la requête /es/ active l'espagnol pour le fil
        response = self.client.get("/es/account/inscription/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("ui_locales=es", response["Location"])
        self.assertIn("prompt=create", response["Location"])
        login = self.client.get("/es/account/connexion/")
        self.assertNotIn("prompt=create", login["Location"])

    def test_number_is_never_stored_in_clear(self):
        account, digits = Account.create_anonymous()
        self.assertNotIn(digits, account.number_digest)
        self.assertEqual(len(account.number_digest), 64)

    def test_recover_with_number(self):
        account, digits = Account.create_anonymous()
        Shortcut.objects.create(account=account, service=self.service)
        response = self.client.post(reverse("core:recover_anonymous"), {"number": format_number(digits)})
        self.assertRedirects(response, reverse("core:account"))
        self.assertEqual(self.client.session[SESSION_KEY], account.pk)
        self.assertContains(self.client.get(reverse("core:home")), self.service.name)

    def test_wrong_number_is_refused(self):
        self.client.post(reverse("core:recover_anonymous"), {"number": "1111 2222 3333 4444"})
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_recovery_is_throttled(self):
        for _ in range(10):
            self.client.post(reverse("core:recover_anonymous"), {"number": "0"})
        account, digits = Account.create_anonymous()
        self.client.post(reverse("core:recover_anonymous"), {"number": digits})
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_shortcuts_can_be_ordered_per_account(self):
        account = Account.create_anonymous()[0]
        service_two = Service.objects.create(name="Agenda", slug="agenda", summary="Agenda personnel.")
        first = Shortcut.objects.create(account=account, service=self.service, position=20)
        second = Shortcut.objects.create(account=account, service=service_two, position=10)
        ordered = list(account.shortcut_set.order_by("position").values_list("service__slug", flat=True))
        self.assertEqual(ordered, ["agenda", self.service.slug])
        self.assertEqual(first.service.name, "Roundcube Webmail")
        self.assertEqual(second.service.name, "Agenda")

    def test_shortcuts_reorder_via_personal_action(self):
        user = get_user_model().objects.create_user("user")
        account = Account.objects.create(user=user)
        service_two = Service.objects.create(name="Agenda", slug="agenda", summary="Agenda personnel.")
        first = Shortcut.objects.create(account=account, service=self.service, position=10)
        second = Shortcut.objects.create(account=account, service=service_two, position=20)

        self.client.force_login(user)
        response = self.client.post(reverse("core:reorder_shortcut", args=[self.service.slug, "down"]))
        self.assertRedirects(response, reverse("core:raccourcis"), fetch_redirect_response=False)
        ordered = list(account.shortcut_set.order_by("position").values_list("service__slug", flat=True))
        self.assertEqual(ordered, ["agenda", self.service.slug])
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.position, 20)
        self.assertEqual(second.position, 10)

    def test_htmx_reorder_returns_partial_without_full_reload(self):
        user = get_user_model().objects.create_user("user")
        account = Account.objects.create(user=user)
        service_two = Service.objects.create(name="Agenda", slug="agenda", summary="Agenda personnel.")
        Shortcut.objects.create(account=account, service=self.service, position=10)
        Shortcut.objects.create(account=account, service=service_two, position=20)

        self.client.force_login(user)
        response = self.client.post(
            reverse("core:reorder_shortcut", args=[self.service.slug, "down"]),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hx-target="#shortcuts-list"')
        self.assertContains(response, "Monter")
        self.assertContains(response, "Descendre")
        self.assertNotContains(response, "302")

    def test_reorder_shortcuts_drag_and_drop(self):
        user = get_user_model().objects.create_user("user")
        account = Account.objects.create(user=user)
        service_two = Service.objects.create(name="Agenda", slug="agenda", summary="Agenda personnel.")
        Shortcut.objects.create(account=account, service=self.service, position=10)
        Shortcut.objects.create(account=account, service=service_two, position=20)

        self.client.force_login(user)
        response = self.client.post(
            reverse("core:reorder_shortcuts"), {"order": f"agenda,{self.service.slug}"},
        )
        self.assertEqual(response.status_code, 200)
        ordered = list(account.shortcut_set.order_by("position").values_list("service__slug", flat=True))
        self.assertEqual(ordered, ["agenda", self.service.slug])

    def test_reorder_shortcuts_requires_an_account(self):
        response = self.client.post(reverse("core:reorder_shortcuts"), {"order": "agenda"})
        self.assertEqual(response.status_code, 403)

    def test_htmx_toggle_returns_partial_with_out_of_band_updates(self):
        response = self.client.post(reverse("core:toggle_shortcut", args=[self.service.slug]), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-pressed="true"')
        self.assertContains(response, 'id="account-panel-body"')
        self.assertContains(response, "hx-swap-oob")
        self.assertContains(response, "Notez votre numéro")
        # Deuxième clic : retrait, pas de nouveau compte.
        self.client.post(reverse("core:toggle_shortcut", args=[self.service.slug]), HTTP_HX_REQUEST="true")
        self.assertEqual(Account.objects.count(), 1)
        self.assertEqual(Shortcut.objects.count(), 0)

    def test_htmx_toggle_refreshes_all_account_lists(self):
        response = self.client.post(
            reverse("core:toggle_shortcut", args=[self.service.slug]),
            {"next": reverse("core:account")},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shortcuts-list"')
        self.assertContains(response, 'id="available-services"')
        self.assertContains(response, 'hx-swap-oob="true"')


class LinkingTests(Base):
    def test_anonymous_shortcuts_join_the_named_account(self):
        self.client.post(reverse("core:toggle_shortcut", args=[self.service.slug]))
        user = get_user_model().objects.create_user("voisine")
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse("core:account")), "Rattacher mes liens")
        self.client.post(reverse("core:link_anonymous"))
        self.assertTrue(Shortcut.objects.filter(account__user=user, service=self.service).exists())
        self.assertFalse(Account.objects.filter(user__isnull=True).exists())


class ServiceApprovalTests(Base):
    def test_shortcut_for_approval_required_service_starts_unapproved(self):
        # roundcube-webmail (fixture) demande une validation : création manuelle d'une
        # boîte courriel par un administrateur avant que le service ne soit actif.
        self.assertTrue(self.service.requires_approval)
        self.client.post(reverse("core:toggle_shortcut", args=[self.service.slug]))
        shortcut = Shortcut.objects.get(service=self.service)
        self.assertFalse(shortcut.approved)

    def test_shortcut_for_ordinary_service_is_approved_immediately(self):
        ordinary = Service.objects.get(slug="gv-je")
        self.assertFalse(ordinary.requires_approval)
        self.client.post(reverse("core:toggle_shortcut", args=[ordinary.slug]))
        shortcut = Shortcut.objects.get(service=ordinary)
        self.assertTrue(shortcut.approved)

    def test_administration_group_can_change_shortcut_and_directoryentry(self):
        from django.contrib.auth.models import Group

        group = Group.objects.get(name="Administration")
        codenames = set(group.permissions.values_list("codename", flat=True))
        self.assertEqual(
            codenames,
            {
                "view_shortcut", "change_shortcut", "view_directoryentry", "change_directoryentry",
                "view_ownershipclaim", "change_ownershipclaim",
                "view_event", "change_event", "view_eventmanagementrequest", "change_eventmanagementrequest",
            },
        )


class EntrySubscriptionNotifyTests(Base):
    def test_notify_toggle_requires_an_existing_subscription(self):
        entry = DirectoryEntry.objects.create(name="Fiche libre", slug="fiche-libre")
        user = get_user_model().objects.create_user("voisine")
        self.client.force_login(user)
        response = self.client.post(reverse("core:toggle_subscription_notify", args=[entry.slug]))
        self.assertEqual(response.status_code, 404)

    def test_notify_toggle_flips_the_flag_and_shows_in_mes_fiches(self):
        entry = DirectoryEntry.objects.create(
            name="Fiche libre", slug="fiche-libre", visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=True,
        )
        user = get_user_model().objects.create_user("voisine")
        self.client.force_login(user)
        self.client.post(reverse("core:toggle_subscription", args=[entry.slug]))

        self.client.post(reverse("core:toggle_subscription_notify", args=[entry.slug]))
        sub = EntrySubscription.objects.get(entry=entry)
        self.assertTrue(sub.notify_email)

        response = self.client.get(reverse("core:mes_fiches"))
        self.assertContains(response, "Fiche libre")


class OwnershipClaimTests(Base):
    @override_settings(OIDC_ENABLED=True)
    def test_anonymous_visitor_is_sent_to_login_and_claim_completes_on_return(self):
        entry = DirectoryEntry.objects.create(
            name="Fiche libre", slug="fiche-libre", visibility=DirectoryEntry.VISIBILITY_PROTECTED,
        )
        response = self.client.post(reverse("core:claim_entry_ownership", args=[entry.slug]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/oidc/authenticate/", response.url)
        self.assertFalse(OwnershipClaim.objects.filter(entry=entry).exists())
        self.assertEqual(self.client.session.get("voisinternet_pending_ownership_claim"), entry.slug)

        # De retour après une connexion Keycloak réussie (simulée par force_login) : la
        # demande, mise de côté, se termine d'elle-même à la prochaine visite de la fiche.
        user = get_user_model().objects.create_user("voisine")
        self.client.force_login(user)
        self.client.get(reverse("core:entry_detail", args=[entry.slug]))
        claim = OwnershipClaim.objects.get(entry=entry)
        self.assertEqual(claim.account.user, user)
        self.assertNotIn("voisinternet_pending_ownership_claim", self.client.session)

    def test_anonymous_visitor_gets_404_when_oidc_disabled(self):
        with override_settings(OIDC_ENABLED=False):
            entry = DirectoryEntry.objects.create(name="Fiche libre", slug="fiche-libre")
            response = self.client.post(reverse("core:claim_entry_ownership", args=[entry.slug]))
            self.assertEqual(response.status_code, 404)

    def test_named_account_can_request_ownership_of_unowned_entry(self):
        entry = DirectoryEntry.objects.create(
            name="Fiche libre", slug="fiche-libre", visibility=DirectoryEntry.VISIBILITY_PROTECTED,
        )
        user = get_user_model().objects.create_user("voisine")
        self.client.force_login(user)
        response = self.client.post(reverse("core:claim_entry_ownership", args=[entry.slug]))
        self.assertRedirects(response, reverse("core:entry_detail", args=[entry.slug]))
        claim = OwnershipClaim.objects.get(entry=entry)
        self.assertEqual(claim.account.user, user)
        self.assertIsNone(claim.approved)
        entry.refresh_from_db()
        self.assertIsNone(entry.owner_id)  # pas encore validée

    def test_cannot_claim_an_already_owned_entry(self):
        owner = Account.objects.create()
        entry = DirectoryEntry.objects.create(name="Fiche prise", slug="fiche-prise", owner=owner)
        user = get_user_model().objects.create_user("voisine")
        self.client.force_login(user)
        response = self.client.post(reverse("core:claim_entry_ownership", args=[entry.slug]))
        self.assertEqual(response.status_code, 404)

    def test_approving_a_claim_transfers_ownership_and_rejects_others(self):
        entry = DirectoryEntry.objects.create(name="Fiche libre", slug="fiche-libre")
        acc1 = Account.objects.create(user=get_user_model().objects.create_user("voisine1"))
        acc2 = Account.objects.create(user=get_user_model().objects.create_user("voisine2"))
        claim1 = OwnershipClaim.objects.create(entry=entry, account=acc1)
        claim2 = OwnershipClaim.objects.create(entry=entry, account=acc2)

        claim1.approved = True
        claim1.save()

        entry.refresh_from_db()
        self.assertEqual(entry.owner_id, acc1.id)
        claim2.refresh_from_db()
        self.assertFalse(claim2.approved)


class EventManagementRequestTests(Base):
    @override_settings(OIDC_ENABLED=True)
    def test_anonymous_visitor_is_sent_to_login_and_request_completes_on_return(self):
        event = Event.objects.create(title="Atelier vélo", slug="atelier-velo", start=timezone.now())
        response = self.client.post(reverse("core:claim_event_management", args=[event.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/oidc/authenticate/", response.url)
        self.assertFalse(EventManagementRequest.objects.filter(event=event).exists())
        self.assertEqual(self.client.session.get("voisinternet_pending_event_management_request"), event.pk)

        # De retour après une connexion Keycloak réussie (simulée par force_login) : la
        # demande, mise de côté, se termine d'elle-même à la prochaine visite de l'évènement.
        user = get_user_model().objects.create_user("voisine")
        self.client.force_login(user)
        self.client.get(reverse("core:event_detail", args=[event.pk]))
        req = EventManagementRequest.objects.get(event=event)
        self.assertEqual(req.account.user, user)
        self.assertNotIn("voisinternet_pending_event_management_request", self.client.session)

    def test_anonymous_visitor_gets_404_when_oidc_disabled(self):
        with override_settings(OIDC_ENABLED=False):
            event = Event.objects.create(title="Atelier vélo", slug="atelier-velo", start=timezone.now())
            response = self.client.post(reverse("core:claim_event_management", args=[event.pk]))
            self.assertEqual(response.status_code, 404)

    def test_named_account_can_request_management(self):
        event = Event.objects.create(title="Atelier vélo", slug="atelier-velo", start=timezone.now())
        user = get_user_model().objects.create_user("voisine")
        self.client.force_login(user)
        response = self.client.post(reverse("core:claim_event_management", args=[event.pk]))
        self.assertRedirects(response, reverse("core:event_detail", args=[event.pk]))
        req = EventManagementRequest.objects.get(event=event)
        self.assertEqual(req.account.user, user)
        self.assertIsNone(req.approved)

    def test_approving_a_request_adds_manager_without_rejecting_others(self):
        # Contrairement à OwnershipClaim (un seul propriétaire), Event.managers accepte
        # plusieurs comptes : valider une demande ne doit pas rejeter les autres.
        event = Event.objects.create(title="Atelier vélo", slug="atelier-velo", start=timezone.now())
        acc1 = Account.objects.create(user=get_user_model().objects.create_user("voisine1"))
        acc2 = Account.objects.create(user=get_user_model().objects.create_user("voisine2"))
        req1 = EventManagementRequest.objects.create(event=event, account=acc1)
        req2 = EventManagementRequest.objects.create(event=event, account=acc2)

        req1.approved = True
        req1.save()

        self.assertIn(acc1, event.managers.all())
        req2.refresh_from_db()
        self.assertIsNone(req2.approved)


class AdministrationTests(Base):
    def test_anonymous_visitor_gets_403(self):
        response = self.client.get(reverse("core:administration"))
        self.assertEqual(response.status_code, 403)

    def test_ordinary_user_gets_403(self):
        user = get_user_model().objects.create_user("voisine")
        self.client.force_login(user)
        response = self.client.get(reverse("core:administration"))
        self.assertEqual(response.status_code, 403)

    def test_administration_group_member_can_review_claim(self):
        from django.contrib.auth.models import Group

        entry = DirectoryEntry.objects.create(name="Fiche libre", slug="fiche-libre")
        acc = Account.objects.create(user=get_user_model().objects.create_user("voisine"))
        claim = OwnershipClaim.objects.create(entry=entry, account=acc)

        admin_user = get_user_model().objects.create_user("admin")
        admin_user.groups.add(Group.objects.get(name="Administration"))
        self.client.force_login(admin_user)

        response = self.client.get(reverse("core:administration"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fiche libre")

        self.client.post(reverse("core:administration_review_claim", args=[claim.pk]), {"decision": "approve"})
        claim.refresh_from_db()
        self.assertTrue(claim.approved)
        entry.refresh_from_db()
        self.assertEqual(entry.owner_id, acc.id)

    def test_administration_group_member_can_toggle_event(self):
        from django.contrib.auth.models import Group

        event = Event.objects.create(title="Atelier vélo", slug="atelier-velo", start=timezone.now(), public=True)
        admin_user = get_user_model().objects.create_user("admin")
        admin_user.groups.add(Group.objects.get(name="Administration"))
        self.client.force_login(admin_user)

        self.client.post(reverse("core:administration_toggle_event", args=[event.pk]), {"field": "featured"})
        event.refresh_from_db()
        self.assertTrue(event.featured)

    def test_administration_group_member_can_review_pending_entry(self):
        from django.contrib.auth.models import Group

        entry = DirectoryEntry.objects.create(
            name="Fiche en attente", slug="fiche-en-attente",
            visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=False,
        )
        admin_user = get_user_model().objects.create_user("admin")
        admin_user.groups.add(Group.objects.get(name="Administration"))
        self.client.force_login(admin_user)

        response = self.client.get(reverse("core:administration"))
        self.assertContains(response, "Fiche en attente")

        self.client.post(reverse("core:administration_review_entry", args=[entry.slug]), {"decision": "approve"})
        entry.refresh_from_db()
        self.assertTrue(entry.approved)
        self.assertEqual(entry.visibility, DirectoryEntry.VISIBILITY_PUBLIC)

    def test_administration_group_member_can_reject_pending_entry(self):
        from django.contrib.auth.models import Group

        entry = DirectoryEntry.objects.create(
            name="Fiche refusée", slug="fiche-refusee",
            visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=False,
        )
        admin_user = get_user_model().objects.create_user("admin")
        admin_user.groups.add(Group.objects.get(name="Administration"))
        self.client.force_login(admin_user)

        self.client.post(reverse("core:administration_review_entry", args=[entry.slug]), {"decision": "reject"})
        entry.refresh_from_db()
        self.assertFalse(entry.approved)
        self.assertEqual(entry.visibility, DirectoryEntry.VISIBILITY_DRAFT)

    def test_administration_group_member_can_review_pending_contribution(self):
        from django.contrib.auth.models import Group

        acc = Account.objects.create(user=get_user_model().objects.create_user("voisine"))
        contribution = Contribution.objects.create(
            account=acc, kind=Contribution.PAYMENT, amount=25, method="virement", date=timezone.localdate(),
        )
        admin_user = get_user_model().objects.create_user("admin")
        admin_user.groups.add(Group.objects.get(name="Administration"))
        self.client.force_login(admin_user)

        response = self.client.get(reverse("core:administration"))
        self.assertContains(response, "25")

        self.client.post(
            reverse("core:administration_review_contribution", args=[contribution.pk]), {"decision": "approve"},
        )
        contribution.refresh_from_db()
        self.assertTrue(contribution.approved)


class DonorPrivacyTests(TestCase):
    def test_only_consenting_donors_are_listed(self):
        Donor.objects.create(name="Voisine généreuse", public=True)
        Donor.objects.create(name="Donateur discret", public=False)
        # Page Wagtail (cms.DonationPage) : pas de nom d'URL Django à inverser.
        response = self.client.get("/fr/contributions/")
        self.assertContains(response, "Voisine généreuse")
        self.assertNotContains(response, "Donateur discret")


class EventQmdTests(Base):
    def setUp(self):
        super().setUp()
        self.event = Event.objects.create(
            title="Conseil des voisins", slug="conseil-des-voisins",
            start=timezone.datetime(2026, 3, 2, 19, 0, tzinfo=timezone.get_current_timezone()),
            location="Ressourcerie créative", description="Ordre du jour et compte-rendu.",
        )

    def test_export_assigns_a_source_uid_if_missing(self):
        from core.qmd import export_event_qmd

        self.assertEqual(self.event.source_uid, "")
        qmd = export_event_qmd(self.event)
        self.event.refresh_from_db()
        self.assertTrue(self.event.source_uid)
        self.assertIn(f"uid: {self.event.source_uid}", qmd)
        self.assertIn("Ordre du jour et compte-rendu.", qmd)

    def test_export_then_import_updates_the_same_event(self):
        from core.qmd import export_event_qmd, import_event_qmd

        qmd = export_event_qmd(self.event)
        imported = import_event_qmd(qmd)

        self.assertEqual(imported.pk, self.event.pk)
        self.assertEqual(Event.objects.count(), 1)
        self.assertEqual(imported.title, "Conseil des voisins")
        self.assertEqual(imported.location, "Ressourcerie créative")

    def test_import_with_unknown_uid_creates_a_new_event(self):
        qmd = (
            "---\n"
            "title: Nouvel atelier\n"
            "uid: brand-new-uid\n"
            "slug: nouvel-atelier\n"
            "start: '2026-04-01T18:00:00+02:00'\n"
            "tags: [Vélo]\n"
            "---\n\n"
            "Un atelier de découverte.\n"
        )
        from core.qmd import import_event_qmd

        event = import_event_qmd(qmd)
        self.assertNotEqual(event.pk, self.event.pk)
        self.assertEqual(event.source_uid, "brand-new-uid")
        self.assertEqual(list(event.tags.values_list("name", flat=True)), ["Vélo"])
        self.assertEqual(Event.objects.count(), 2)

    def test_import_without_start_on_a_new_event_raises(self):
        from core.qmd import import_event_qmd

        qmd = "---\ntitle: Sans date\nuid: no-date-uid\n---\n\nTexte.\n"
        with self.assertRaises(ValueError):
            import_event_qmd(qmd)


class AgendaTests(Base):
    def test_event_detail_page(self):
        event = Event.objects.create(
            title="Atelier vélo", slug="atelier-velo",
            start=timezone.now(), location="Ressourcerie créative",
            description="Réparons nos vélos ensemble.",
        )
        response = self.client.get(reverse("core:event_detail", args=[event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Atelier vélo")
        self.assertContains(response, reverse("core:event_ics", args=[event.pk]))

    def test_non_public_event_detail_is_404(self):
        event = Event.objects.create(title="Réunion privée", slug="reunion-privee", start=timezone.now(), public=False)
        response = self.client.get(reverse("core:event_detail", args=[event.pk]))
        self.assertEqual(response.status_code, 404)

    def test_non_public_event_detail_is_visible_to_its_manager(self):
        event = Event.objects.create(title="Réunion privée", slug="reunion-privee", start=timezone.now(), public=False)
        user = get_user_model().objects.create_user("voisine")
        event.managers.add(Account.objects.create(user=user))
        self.client.force_login(user)
        response = self.client.get(reverse("core:event_detail", args=[event.pk]))
        self.assertEqual(response.status_code, 200)

    def test_event_detail_links_to_previous_and_next_public_events(self):
        now = timezone.now()
        earlier = Event.objects.create(title="Atelier précédent", slug="atelier-precedent", start=now - timezone.timedelta(days=2))
        current = Event.objects.create(title="Atelier courant", slug="atelier-courant", start=now)
        later = Event.objects.create(title="Atelier suivant", slug="atelier-suivant", start=now + timezone.timedelta(days=2))
        hidden = Event.objects.create(
            title="Atelier caché", slug="atelier-cache", start=now + timezone.timedelta(days=1), public=False,
        )

        response = self.client.get(reverse("core:event_detail", args=[current.pk]))
        self.assertEqual(response.context["previous_event"], earlier)
        self.assertEqual(response.context["next_event"], later)
        self.assertContains(response, "Atelier précédent")
        self.assertContains(response, "Atelier suivant")
        self.assertNotContains(response, "Atelier caché")
        self.assertContains(response, reverse("core:event_detail", args=[earlier.pk]))
        self.assertContains(response, reverse("core:event_detail", args=[later.pk]))

    def test_event_ics_download(self):
        event = Event.objects.create(
            title="Atelier vélo", slug="atelier-velo",
            start=timezone.now(), end=timezone.now(), location="Ressourcerie créative",
        )
        response = self.client.get(reverse("core:event_ics", args=[event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/calendar; charset=utf-8")
        content = response.content.decode()
        self.assertIn("BEGIN:VEVENT", content)
        self.assertIn("SUMMARY:Atelier vélo", content)
        self.assertIn("LOCATION:Ressourcerie créative", content)

    def test_event_interest_toggle_switches_level_then_removes(self):
        event = Event.objects.create(title="Atelier vélo", slug="atelier-velo", start=timezone.now(), public=True)
        user = get_user_model().objects.create_user("voisine")
        self.client.force_login(user)

        self.client.post(reverse("core:toggle_event_interest", args=[event.pk]), {"level": "interested"})
        interest = EventInterest.objects.get(event=event)
        self.assertEqual(interest.level, EventInterest.INTERESTED)

        # Même compte, niveau différent : met à jour plutôt que de dupliquer.
        self.client.post(reverse("core:toggle_event_interest", args=[event.pk]), {"level": "going"})
        interest.refresh_from_db()
        self.assertEqual(interest.level, EventInterest.GOING)

        # Reposter le même niveau retire l'intérêt (bascule).
        self.client.post(reverse("core:toggle_event_interest", args=[event.pk]), {"level": "going"})
        self.assertFalse(EventInterest.objects.filter(event=event).exists())

    def test_event_interest_notify_toggle_and_listing(self):
        event = Event.objects.create(title="Atelier vélo", slug="atelier-velo", start=timezone.now(), public=True)
        user = get_user_model().objects.create_user("voisine")
        self.client.force_login(user)
        self.client.post(reverse("core:toggle_event_interest", args=[event.pk]), {"level": "interested"})

        self.client.post(reverse("core:toggle_event_interest_notify", args=[event.pk]))
        interest = EventInterest.objects.get(event=event)
        self.assertTrue(interest.notify_email)

        response = self.client.get(reverse("core:mes_evenements"))
        self.assertContains(response, "Atelier vélo")


class MesEvenementsTests(Base):
    def test_creating_an_event_makes_the_account_a_manager_and_stays_unpublished(self):
        user = get_user_model().objects.create_user("voisine")
        self.client.force_login(user)
        response = self.client.post(reverse("core:mes_evenements"), {
            "title_fr": "Atelier vélo", "start": "2026-10-01 10:00:00",
            "description_fr": "", "location_fr": "", "online_url": "", "tags": [],
        })
        event = Event.objects.get(title="Atelier vélo")
        self.assertRedirects(response, reverse("core:event_detail", args=[event.pk]))
        self.assertFalse(event.public)
        acc = Account.objects.get(user=user)
        self.assertIn(event, acc.managed_events.all())
        # La page d'aperçu dit clairement où en est l'évènement.
        self.assertContains(self.client.get(response["Location"]), "En attente de publication")

    def test_creation_notifies_administration_and_publication_notifies_the_creator(self):
        from django.contrib.auth.models import Group

        admin = get_user_model().objects.create_user("admin", email="admin@example.org")
        admin.groups.add(Group.objects.get_or_create(name="Administration")[0])
        creator = get_user_model().objects.create_user("voisine", email="voisine@example.org")
        self.client.force_login(creator)
        self.client.post(reverse("core:mes_evenements"), {
            "title_fr": "Atelier vélo", "start": "2026-10-01 10:00:00",
            "description_fr": "", "location_fr": "", "online_url": "", "tags": [],
        })
        self.assertEqual([m.to for m in mail.outbox], [["admin@example.org"]])
        event = Event.objects.get(title="Atelier vélo")

        self.client.force_login(admin)
        self.client.post(reverse("core:administration_toggle_event", args=[event.pk]), {"field": "public"})
        self.assertEqual(mail.outbox[-1].to, ["voisine@example.org"])
        event.refresh_from_db()
        self.assertTrue(event.public)

    def test_visiting_my_events_does_not_create_an_account(self):
        response = self.client.get(reverse("core:mes_evenements"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Account.objects.exists())
        self.assertNotContains(response, "Votre numéro de compte anonyme")

    def test_event_form_follows_the_active_browsing_language(self):
        # Contrairement à DirectoryEntryForm (toujours _fr) : un évènement se crée/modifie
        # dans la langue qu'on est en train de parcourir.
        from django.utils import translation

        # LocaleMiddleware active "en" pour la durée de la requête (préfixe d'URL) mais ne
        # la redésactive jamais après coup : sans ce cleanup, "en" reste la langue active
        # pour tout le reste du processus de test (reverse() dans les tests suivants se
        # mettrait alors à générer des URL /en/... au lieu de /fr/...).
        self.addCleanup(translation.deactivate_all)

        user = get_user_model().objects.create_user("voisine-en")
        self.client.force_login(user)
        response = self.client.post("/en/agenda/mes-evenements/", {
            "title_en": "Bike workshop", "start": "2026-10-01 10:00:00",
            "description_en": "", "location_en": "", "online_url": "", "tags": [],
        })
        event = Event.objects.get(title_en="Bike workshop")
        self.assertRedirects(response, f"/en/agenda/{event.pk}/")
        acc = Account.objects.get(user=user)
        self.assertIn(event, acc.managed_events.all())

    def test_only_a_manager_can_edit_or_delete_their_event(self):
        owner = get_user_model().objects.create_user("voisine")
        other = get_user_model().objects.create_user("autre")
        event = Event.objects.create(title="Atelier vélo", slug="atelier-velo", start=timezone.now(), public=False)
        event.managers.add(Account.objects.create(user=owner))
        Account.objects.create(user=other)

        self.client.force_login(other)
        response = self.client.get(reverse("core:evenement_modifier", args=[event.pk]))
        self.assertEqual(response.status_code, 404)  # même comportement que fiche_modifier
        self.client.post(reverse("core:evenement_supprimer", args=[event.pk]))
        event.refresh_from_db()  # toujours là : la suppression n'a rien trouvé pour ce compte

        self.client.force_login(owner)
        response = self.client.post(reverse("core:evenement_modifier", args=[event.pk]), {
            "title_fr": "Atelier vélo (mis à jour)", "start": "2026-10-01 10:00:00",
            "description_fr": "", "location_fr": "", "online_url": "", "tags": [],
        })
        self.assertRedirects(response, reverse("core:event_detail", args=[event.pk]))
        event.refresh_from_db()
        self.assertEqual(event.title, "Atelier vélo (mis à jour)")

        self.client.post(reverse("core:evenement_supprimer", args=[event.pk]))
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())


class AudienceTests(Base):
    def test_home_asks_who_you_are(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Vous êtes…")
        self.assertContains(response, reverse("core:groupes"))

    def test_groupes_lists_audiences_with_join_buttons(self):
        self.client.post(reverse("core:toggle_shortcut", args=[self.service.slug]))  # crée un compte
        response = self.client.get(reverse("core:groupes"))
        self.assertContains(response, Audience.objects.get(slug="associations").name)
        self.assertContains(response, 'class="add"')

    def test_reorder_memberships_drag_and_drop(self):
        user = get_user_model().objects.create_user("user")
        account = Account.objects.create(user=user)
        associations = Audience.objects.get(slug="associations")
        other = Audience.objects.create(name="Un particulier", slug="particulier")
        Membership.objects.create(account=account, audience=associations, position=10)
        Membership.objects.create(account=account, audience=other, position=20)

        self.client.force_login(user)
        response = self.client.post(
            reverse("core:reorder_memberships"), {"order": "particulier,associations"},
        )
        self.assertEqual(response.status_code, 200)
        ordered = list(account.membership_set.order_by("position").values_list("audience__slug", flat=True))
        self.assertEqual(ordered, ["particulier", "associations"])

    def test_partnership_audience_offers_no_join_button(self):
        # Aucune audience du fixture n'est un partenariat à ce jour : on en crée une pour
        # vérifier que le cas spécial (pas de bouton « Adhérer », un mailto à la place) marche.
        Audience.objects.create(name="Une institution", slug="une-institution", pitch="Test", partnership=True)
        self.client.post(reverse("core:toggle_shortcut", args=[self.service.slug]))  # crée un compte
        response = self.client.get(reverse("core:groupes"))
        self.assertContains(response, "Proposer un partenariat")

    def test_unknown_directory_sector_is_404(self):
        self.assertEqual(self.client.get(reverse("core:annuaire_pour", args=["inconnu"])).status_code, 404)

    def test_directory_entry_detail_page(self):
        sector = DirectorySector.objects.create(name="Civisme", slug="civisme")
        entry = DirectoryEntry.objects.create(
            name="Ada Matus", slug="ada-matus", sector=sector,
            tagline="Autrice Compositrice", description="Un groupe de soutien culturel.",
            visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=True,
        )
        response = self.client.get(reverse("core:entry_detail", args=[entry.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ada Matus")
        self.assertContains(response, "Autrice Compositrice")
        self.assertContains(response, reverse("core:toggle_subscription", args=[entry.slug]))

    def test_draft_directory_entry_detail_is_404(self):
        entry = DirectoryEntry.objects.create(
            name="Fiche privée", slug="fiche-privee", visibility=DirectoryEntry.VISIBILITY_DRAFT,
        )
        response = self.client.get(reverse("core:entry_detail", args=[entry.slug]))
        self.assertEqual(response.status_code, 404)

    def test_protected_directory_entry_requires_an_account(self):
        entry = DirectoryEntry.objects.create(
            name="Fiche protégée", slug="fiche-protegee", visibility=DirectoryEntry.VISIBILITY_PROTECTED,
        )
        anonymous_response = self.client.get(reverse("core:entry_detail", args=[entry.slug]))
        self.assertEqual(anonymous_response.status_code, 404)
        self.client.post(reverse("core:toggle_shortcut", args=[self.service.slug]))  # crée un compte
        response = self.client.get(reverse("core:entry_detail", args=[entry.slug]))
        self.assertEqual(response.status_code, 200)

    def test_protected_directory_entry_absent_from_listing(self):
        entry = DirectoryEntry.objects.create(
            name="Fiche protégée", slug="fiche-protegee", visibility=DirectoryEntry.VISIBILITY_PROTECTED,
        )
        response = self.client.get(reverse("core:annuaire"))
        self.assertNotContains(response, reverse("core:entry_detail", args=[entry.slug]))

    def test_owner_can_preview_their_own_draft(self):
        acc = Account.objects.create()
        entry = DirectoryEntry.objects.create(
            name="Fiche privée", slug="fiche-privee", visibility=DirectoryEntry.VISIBILITY_DRAFT, owner=acc,
        )
        session = self.client.session
        session[SESSION_KEY] = acc.pk
        session.save()
        response = self.client.get(reverse("core:entry_detail", args=[entry.slug]))
        self.assertEqual(response.status_code, 200)

    def test_owner_can_toggle_publication(self):
        acc = Account.objects.create()
        entry = DirectoryEntry.objects.create(
            name="Fiche à publier", slug="fiche-a-publier", visibility=DirectoryEntry.VISIBILITY_DRAFT, owner=acc,
        )
        session = self.client.session
        session[SESSION_KEY] = acc.pk
        session.save()
        self.client.post(reverse("core:toggle_publication", args=[entry.slug]))
        entry.refresh_from_db()
        self.assertEqual(entry.visibility, DirectoryEntry.VISIBILITY_PUBLIC)
        # En attente de validation par le groupe « Administration » : pas encore publique.
        self.assertFalse(entry.approved)
        self.client.post(reverse("core:toggle_publication", args=[entry.slug]))
        entry.refresh_from_db()
        self.assertEqual(entry.visibility, DirectoryEntry.VISIBILITY_DRAFT)

    def test_non_owner_cannot_toggle_publication(self):
        entry = DirectoryEntry.objects.create(
            name="Fiche protégée", slug="fiche-a-proteger", visibility=DirectoryEntry.VISIBILITY_DRAFT,
        )
        response = self.client.post(reverse("core:toggle_publication", args=[entry.slug]))
        self.assertEqual(response.status_code, 404)
        entry.refresh_from_db()
        self.assertEqual(entry.visibility, DirectoryEntry.VISIBILITY_DRAFT)

    def test_directory_list_links_to_entry_detail(self):
        entry = DirectoryEntry.objects.create(
            name="Ada Matus", slug="ada-matus", visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=True,
        )
        response = self.client.get(reverse("core:annuaire"))
        self.assertContains(response, reverse("core:entry_detail", args=[entry.slug]))

    def test_pending_public_directory_entry_is_hidden_until_approved(self):
        acc = Account.objects.create()
        entry = DirectoryEntry.objects.create(
            name="Fiche en attente", slug="fiche-en-attente", owner=acc,
            visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=False,
        )
        response = self.client.get(reverse("core:entry_detail", args=[entry.slug]))
        self.assertEqual(response.status_code, 404)
        listing = self.client.get(reverse("core:annuaire"))
        self.assertNotContains(listing, reverse("core:entry_detail", args=[entry.slug]))
        # Le propriétaire, lui, peut toujours prévisualiser sa fiche en attente.
        session = self.client.session
        session[SESSION_KEY] = acc.pk
        session.save()
        owner_response = self.client.get(reverse("core:entry_detail", args=[entry.slug]))
        self.assertEqual(owner_response.status_code, 200)


def _captcha(answer=8, a=3, b=5):
    """Champs anti-robot valides (3 + 5 = 8) d'un ContactMessageForm."""
    return {"captcha_answer": answer, "captcha_token": ContactMessageForm.make_captcha_token(a, b)}


@override_settings(CONTACT_FORMS_ENABLED=True)
class ContactCaptchaTests(Base):
    def setUp(self):
        super().setUp()
        self.author = Author.objects.create(name="Jean Dupont", email="jean@example.org")
        self.url = reverse("core:author_detail", args=[self.author.pk])
        self.data = {"sender_name": "Alice", "sender_email": "alice@example.org", "message": "Bonjour !", "website": ""}

    def test_form_shows_a_question_and_a_signed_token(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Combien font")
        self.assertContains(response, 'name="captcha_token"')

    def test_wrong_answer_is_refused_and_question_is_kept(self):
        response = self.client.post(self.url, {**self.data, **_captcha(answer=9)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Réponse incorrecte")
        self.assertContains(response, "Combien font 3 + 5")
        self.assertEqual(AuthorMessage.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_missing_captcha_is_refused(self):
        self.client.post(self.url, self.data)
        self.assertEqual(AuthorMessage.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_forged_token_is_refused(self):
        response = self.client.post(self.url, {**self.data, "captcha_answer": 8, "captcha_token": "3:5:forge"})
        self.assertContains(response, "Anti-robot expiré")
        self.assertEqual(AuthorMessage.objects.count(), 0)

    def test_expired_token_is_refused(self):
        token = ContactMessageForm.make_captcha_token(3, 5)
        with mock.patch("django.core.signing.time.time", return_value=timezone.now().timestamp() + 3600):
            response = self.client.post(self.url, {**self.data, "captcha_answer": 8, "captcha_token": token})
        self.assertContains(response, "Anti-robot expiré")
        self.assertEqual(AuthorMessage.objects.count(), 0)


@override_settings(CONTACT_FORMS_ENABLED=False)
class ContactFormsDisabledTests(Base):
    def test_forms_are_hidden_and_posts_send_nothing(self):
        author = Author.objects.create(name="Jean Dupont", email="jean@example.org")
        entry = DirectoryEntry.objects.create(
            name="Fiche Test", slug="fiche-test", email="fiche@example.org",
            visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=True,
        )
        data = {"sender_name": "A", "sender_email": "a@example.org", "message": "Salut", "website": "", **_captcha()}
        for url, marker in ((reverse("core:author_detail", args=[author.pk]), "author-contact-title"),
                            (reverse("core:entry_detail", args=[entry.slug]), "entry-contact-title")):
            self.assertNotContains(self.client.get(url), marker)
            self.client.post(url, data)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AuthorMessage.objects.count() + EntryMessage.objects.count(), 0)


@override_settings(CONTACT_FORMS_ENABLED=True)
class AuthorContactTests(Base):
    def setUp(self):
        super().setUp()
        self.author = Author.objects.create(name="Jean Dupont", email="jean@example.org")

    def test_page_without_email_hides_contact_form(self):
        author = Author.objects.create(name="Sans e-mail")
        response = self.client.get(reverse("core:author_detail", args=[author.pk]))
        self.assertNotContains(response, 'id="author-contact-title"')

    def test_valid_message_is_sent_and_recorded(self):
        response = self.client.post(reverse("core:author_detail", args=[self.author.pk]), {
            "sender_name": "Alice", "sender_email": "alice@example.org", "message": "Bonjour !", "website": "", **_captcha(),
        })
        self.assertRedirects(response, reverse("core:author_detail", args=[self.author.pk]))
        self.assertEqual(AuthorMessage.objects.filter(author=self.author).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["jean@example.org"])
        self.assertEqual(mail.outbox[0].reply_to, ["alice@example.org"])

    def test_honeypot_silently_drops_message(self):
        self.client.post(reverse("core:author_detail", args=[self.author.pk]), {
            "sender_name": "Robot", "sender_email": "bot@example.org", "message": "spam",
            "website": "http://spam.example", **_captcha(),
        })
        self.assertEqual(AuthorMessage.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_contact_form_is_throttled(self):
        for _ in range(5):
            self.client.post(reverse("core:author_detail", args=[self.author.pk]), {
                "sender_name": "Alice", "sender_email": "alice@example.org", "message": "Bonjour !", "website": "", **_captcha(),
            })
        self.assertEqual(len(mail.outbox), 5)
        response = self.client.post(reverse("core:author_detail", args=[self.author.pk]), {
            "sender_name": "Alice", "sender_email": "alice@example.org", "message": "Encore un.", "website": "", **_captcha(),
        }, follow=True)
        self.assertEqual(len(mail.outbox), 5)  # le 6e message n'est pas parti
        self.assertContains(response, "Trop de messages envoyés récemment")

    def test_smtp_failure_still_records_the_message_without_crashing(self):
        # Incident réel : un serveur SMTP injoignable/mal configuré (mauvais port,
        # connexion qui traîne) ne doit jamais faire planter la requête — voir
        # settings.EMAIL_TIMEOUT et _process_contact_form.
        from smtplib import SMTPConnectError

        with mock.patch("core.views.EmailMessage.send", side_effect=SMTPConnectError(421, "down")):
            response = self.client.post(reverse("core:author_detail", args=[self.author.pk]), {
                "sender_name": "Alice", "sender_email": "alice@example.org", "message": "Bonjour !", "website": "", **_captcha(),
            }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AuthorMessage.objects.filter(author=self.author).count(), 1)
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(response, "son envoi par e-mail a échoué")


class EntryDetailPhotoTests(Base):
    def test_logo_shown_when_no_promo_photo_or_gallery(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        entry = DirectoryEntry.objects.create(
            name="Fiche avec logo", slug="fiche-avec-logo",
            visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=True,
            logo=SimpleUploadedFile("logo.gif", b"GIF87a", content_type="image/gif"),
        )
        response = self.client.get(reverse("core:entry_detail", args=[entry.slug]))
        self.assertContains(response, entry.logo.url)


@override_settings(CONTACT_FORMS_ENABLED=True)
class EntryContactTests(Base):
    def setUp(self):
        super().setUp()
        self.entry = DirectoryEntry.objects.create(
            name="Fiche Test", slug="fiche-test", email="fiche@example.org",
            visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=True,
        )

    def test_entry_without_email_hides_contact_form_and_mailto(self):
        entry = DirectoryEntry.objects.create(
            name="Sans e-mail", slug="sans-email",
            visibility=DirectoryEntry.VISIBILITY_PUBLIC, approved=True,
        )
        response = self.client.get(reverse("core:entry_detail", args=[entry.slug]))
        self.assertNotContains(response, 'id="entry-contact-title"')

    def test_email_is_never_shown_as_a_mailto_link(self):
        response = self.client.get(reverse("core:entry_detail", args=[self.entry.slug]))
        self.assertNotContains(response, "mailto:fiche@example.org")

    def test_valid_message_is_sent_and_recorded(self):
        response = self.client.post(reverse("core:entry_detail", args=[self.entry.slug]), {
            "sender_name": "Alice", "sender_email": "alice@example.org", "message": "Bonjour !", "website": "", **_captcha(),
        })
        self.assertRedirects(response, reverse("core:entry_detail", args=[self.entry.slug]))
        self.assertEqual(EntryMessage.objects.filter(entry=self.entry).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["fiche@example.org"])
        self.assertEqual(mail.outbox[0].reply_to, ["alice@example.org"])

    def test_honeypot_silently_drops_message(self):
        self.client.post(reverse("core:entry_detail", args=[self.entry.slug]), {
            "sender_name": "Robot", "sender_email": "bot@example.org", "message": "spam",
            "website": "http://spam.example", **_captcha(),
        })
        self.assertEqual(EntryMessage.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)


class WikiJsSearchTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(WIKIJS_API_KEY="")
    def test_disabled_without_api_key(self):
        from core.wikijs import search

        with mock.patch("core.wikijs.urlopen") as urlopen:
            self.assertEqual(search("permanence"), [])
        urlopen.assert_not_called()

    @override_settings(WIKIJS_API_KEY="test-token")
    def test_parses_successful_response(self):
        from core.wikijs import search

        payload = {
            "data": {"pages": {"search": {"results": [
                {"title": "Permanences", "description": "Où et quand", "path": "guide/permanences", "locale": "fr"},
            ]}}},
        }
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(payload).encode("utf-8")
        with mock.patch("core.wikijs.urlopen", return_value=response):
            results = search("permanence")
        self.assertEqual(results, [{
            "title": "Permanences", "description": "Où et quand",
            "url": f"{settings.GUIDE_URL.rstrip('/')}/fr/guide/permanences",
        }])

    @override_settings(WIKIJS_API_KEY="test-token")
    def test_degrades_gracefully_when_unreachable(self):
        from core.wikijs import search

        with mock.patch("core.wikijs.urlopen", side_effect=URLError("down")):
            self.assertEqual(search("permanence"), [])

    @override_settings(WIKIJS_API_KEY="test-token")
    def test_filters_out_other_language_results(self):
        # Le paramètre "locale" envoyé à Wiki.js n'est pas garanti d'être respecté côté
        # serveur (selon son moteur de recherche) : on ne fait pas confiance à la seule
        # réponse de l'API et on refiltre nous-mêmes par langue active.
        from core.wikijs import search

        payload = {
            "data": {"pages": {"search": {"results": [
                {"title": "Permanences", "description": "Où et quand", "path": "guide/permanences", "locale": "fr"},
                {"title": "Opening hours", "description": "When and where", "path": "guide/opening-hours", "locale": "en"},
            ]}}},
        }
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(payload).encode("utf-8")
        with mock.patch("core.wikijs.urlopen", return_value=response):
            results = search("permanence")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Permanences")


class DonationFlowTests(Base):
    def test_mes_dons_page_lists_contributions_and_form(self):
        self.client.post(reverse("core:faire_don"), {
            "kind": "pledge", "amount": "25", "method": "virement", "date": "2026-01-01", "note": "",
        })
        response = self.client.get(reverse("core:mes_dons"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "25")
        self.assertContains(response, "Faire un don")

    def test_pledge_is_auto_approved(self):
        self.client.post(reverse("core:faire_don"), {
            "kind": "pledge", "amount": "25", "method": "virement", "date": "2026-01-01", "note": "",
        })
        contribution = Contribution.objects.get()
        self.assertEqual(contribution.kind, Contribution.PLEDGE)
        self.assertTrue(contribution.approved)

    def test_payment_awaits_validation(self):
        self.client.post(reverse("core:faire_don"), {
            "kind": "payment", "amount": "25", "method": "cheque", "date": "2026-01-01", "note": "",
        })
        contribution = Contribution.objects.get()
        self.assertEqual(contribution.kind, Contribution.PAYMENT)
        self.assertIsNone(contribution.approved)

    def test_faire_don_redirects_to_confirmation_page(self):
        response = self.client.post(reverse("core:faire_don"), {
            "kind": "payment", "amount": "25", "method": "paypal", "date": "2026-01-01", "note": "",
        })
        self.assertRedirects(response, f"{reverse('core:faire_don_merci')}?amount=25&method=paypal&kind=payment")

    def test_confirmation_page_prefills_paypal_amount(self):
        response = self.client.get(reverse("core:faire_don_merci"), {"amount": "25", "method": "paypal", "kind": "payment"})
        self.assertContains(response, "hosted_button_id=BPUUS6H6TP62Y&amp;amount=25")
        self.assertContains(response, "en attente")

    def test_confirmation_page_shows_donation_page_cards_for_bank_transfer(self):
        from cms.models import DonationPage

        donation_page = DonationPage.objects.live().first()
        response = self.client.get(reverse("core:faire_don_merci"), {"amount": "25", "method": "virement", "kind": "pledge"})
        self.assertNotContains(response, "en attente")  # une promesse n'attend rien
        for block in donation_page.cards:
            self.assertContains(response, block.value["title"])


class ParcoursTests(Base):
    def setUp(self):
        super().setUp()
        from core.models import Mission, MissionStep

        self.mission = Mission.objects.create(slug="courriel", title="Ma boîte courriel", summary="Lire et écrire")
        self.manual = MissionStep.objects.create(mission=self.mission, position=1, title="Ouvrir le webmail")
        self.auto = MissionStep.objects.create(mission=self.mission, position=2, title="Un raccourci", auto_check="shortcut")

    def test_pages_render_without_account_and_create_none(self):
        self.assertContains(self.client.get(reverse("core:parcours")), "Ma boîte courriel")
        page = self.client.get(reverse("core:parcours_detail", args=["courriel"]))
        self.assertContains(page, "Ouvrir le webmail")
        self.assertContains(page, "0 sur 2")
        self.assertFalse(Account.objects.exists())

    def test_ticking_without_account_asks_to_open_one(self):
        response = self.client.post(reverse("core:parcours_step", args=[self.manual.pk]))
        self.assertRedirects(response, reverse("core:account"))
        self.assertFalse(Account.objects.exists())

    def test_manual_and_detected_steps_lead_to_completion(self):
        account, _digits = Account.create_anonymous()
        session = self.client.session
        session["voisinternet_account"] = account.pk
        session.save()
        from core.accounts import SESSION_KEY
        session = self.client.session
        session[SESSION_KEY] = account.pk
        session.save()

        self.client.post(reverse("core:parcours_step", args=[self.manual.pk]))
        page = self.client.get(reverse("core:parcours_detail", args=["courriel"]))
        self.assertContains(page, "1 sur 2")
        self.assertNotContains(page, "Bravo, parcours terminé")

        Shortcut.objects.create(account=account, service=self.service)  # étape détectée
        page = self.client.get(reverse("core:parcours_detail", args=["courriel"]))
        self.assertContains(page, "Bravo, parcours terminé")

        # Une étape détectée ne se coche pas à la main.
        self.assertEqual(self.client.post(reverse("core:parcours_step", args=[self.auto.pk])).status_code, 404)
        # Décocher l'étape manuelle la remet à faire.
        self.client.post(reverse("core:parcours_step", args=[self.manual.pk]))
        self.assertContains(self.client.get(reverse("core:parcours_detail", args=["courriel"])), "1 sur 2")


@override_settings(ANONYMOUS_ACCOUNTS="discret")
class AnonymeDiscretTests(Base):
    """Réglage par défaut : le compte anonyme existe mais ne se voit pas et ne se crée jamais tout seul."""

    def test_visiting_pages_creates_no_account(self):
        for name in ["home", "account", "agenda", "mes_fiches", "mes_evenements", "parcours"]:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(f"core:{name}")).status_code, 200)
        # « raccourcis » et « groupes » renvoient vers « Mon compte » tant qu'il n'y a pas de compte.
        for name in ["raccourcis", "groupes"]:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(f"core:{name}")).status_code, 302)
        self.assertFalse(Account.objects.exists())

    def test_clicking_add_shortcut_asks_for_an_account_instead_of_creating_one(self):
        response = self.client.post(reverse("core:toggle_shortcut", args=[self.service.slug]))
        self.assertRedirects(response, reverse("core:account"), fetch_redirect_response=False)
        self.assertFalse(Account.objects.exists())
        self.assertFalse(Shortcut.objects.exists())
        # htmx : pas de page injectée dans un fragment, une redirection côté navigateur.
        response = self.client.post(reverse("core:toggle_shortcut", args=[self.service.slug]), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Redirect"], reverse("core:account"))
        self.assertFalse(Account.objects.exists())

    def test_same_for_groups_and_events_and_directory(self):
        from core.models import Audience
        audience = Audience.objects.first()
        self.client.post(reverse("core:toggle_membership", args=[audience.slug]))
        self.client.post(reverse("core:mes_fiches"), {"name_fr": "Une fiche"})
        self.client.post(reverse("core:mes_evenements"), {"title_fr": "X", "start": "2026-10-01 10:00:00"})
        self.assertFalse(Account.objects.exists())

    def test_no_visible_anonymous_button_but_still_reachable_in_details(self):
        for path in [reverse("core:home"), reverse("core:account")]:
            page = self.client.get(path).content.decode()
            self.assertNotIn("Rester anonyme", page)
            self.assertNotIn("Me connecter ou rester anonyme", page)
        account = self.client.get(reverse("core:account"))
        self.assertContains(account, 'class="anon-discret"')   # discret, mais pas supprimé
        self.assertContains(account, reverse("core:create_anonymous"))

    def test_explicit_creation_still_works_and_shows_the_number(self):
        self.client.post(reverse("core:create_anonymous"))
        self.assertEqual(Account.objects.count(), 1)
        self.assertContains(self.client.get(reverse("core:home")), "Votre numéro de compte anonyme")

    def test_a_donation_is_a_deliberate_act_and_keeps_working(self):
        self.client.post(reverse("core:faire_don"), {"amount": "10", "method": "cheque", "kind": "pledge", "date": "2026-10-28", "note": ""})
        self.assertEqual(Account.objects.count(), 1)


@override_settings(ANONYMOUS_ACCOUNTS="ferme")
class AnonymeFermeTests(Base):
    def test_no_creation_at_all_but_recovery_form_remains(self):
        response = self.client.post(reverse("core:create_anonymous"))
        self.assertRedirects(response, reverse("core:account"), fetch_redirect_response=False)
        self.assertFalse(Account.objects.exists())
        page = self.client.get(reverse("core:account"))
        self.assertNotContains(page, reverse("core:create_anonymous"))
        self.assertContains(page, reverse("core:recover_anonymous"))   # les numéros existants fonctionnent encore

    def test_existing_anonymous_account_keeps_working(self):
        account, digits = Account.create_anonymous()
        self.client.post(reverse("core:recover_anonymous"), {"number": digits})
        self.client.post(reverse("core:toggle_shortcut", args=[self.service.slug]))
        self.assertTrue(Shortcut.objects.filter(account=account).exists())


class RobotsEtCalendrierTests(Base):
    def test_robots_txt_keeps_robots_out_of_useless_pages(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        for rule in ["Disallow: /*/account/", "Disallow: /*?mois=", "Disallow: /*/cms/"]:
            self.assertContains(response, rule)

    def test_calendar_months_are_bounded(self):
        today = timezone.localdate()
        courant = self.client.get(reverse("core:home")).context["agenda_calendar"]["month_label"]
        # Mois absurdes (passé lointain, futur lointain, valeur illisible) : retombent sur le mois courant.
        for valeur in ["1997-07", f"{today.year + 10}-01", "n-importe-quoi"]:
            with self.subTest(mois=valeur):
                self.assertEqual(self.client.get(reverse("core:home") + f"?mois={valeur}").context["agenda_calendar"]["month_label"], courant)
        # Un mois dans la fenêtre (il y a un an) reste accessible.
        proche = self.client.get(reverse("core:home") + f"?mois={today.year - 1}-{today.month:02d}")
        self.assertEqual(proche.context["agenda_calendar"]["month_label"].year, today.year - 1)

    def test_calendar_pages_with_a_month_are_noindex(self):
        self.assertContains(self.client.get(reverse("core:home") + "?mois=2026-10"), 'name="robots" content="noindex, nofollow"')
        self.assertNotContains(self.client.get(reverse("core:home")), 'name="robots"')
        self.assertContains(self.client.get(reverse("core:account")), 'name="robots" content="noindex, nofollow"')


class AnciennesAdressesTests(Base):
    def test_old_site_addresses_redirect_permanently_and_keep_the_language(self):
        self.addCleanup(translation.activate, "fr")  # les requêtes /en/ et /ar/ activent leur langue pour le fil
        for langue in ["fr", "en", "ar"]:
            with self.subTest(langue=langue):
                response = self.client.get(f"/{langue}/association/")
                self.assertEqual(response.status_code, 301)
                self.assertEqual(response["Location"], f"/{langue}/grandsvoisins/")

    def test_old_site_fr_fr_addresses(self):
        from urllib.parse import quote
        DirectoryEntry.objects.create(name="Carton Plein", slug="carton-plein")
        Event.objects.create(title="Bonne année 2025", slug="bonne-annee-2025", start=timezone.now(), public=True)
        event = Event.objects.get(slug="bonne-annee-2025")
        cas = {
            "/fr-fr/": "/fr/",
            "/fr-fr/association/conseils-des-voisins/25e/": "/fr/grandsvoisins/",
            "/fr-fr/activités/": "/fr/activites/",
            "/fr-fr/annuaire/carton-plein/": "/fr/annuaire/carton-plein/",
            "/fr-fr/annuaire/inconnu/": "/fr/annuaire/",
            "/fr-fr/blog/introuvable/": "/fr/blog/",
            "/fr-fr/numerique/proposition-annuaire/": "/fr/numerique/",
            "/fr-fr/agenda/" + quote("bonne-année-2025") + "/": f"/fr/agenda/{event.pk}/",
            "/fr-fr/agenda/autre-chose/": "/fr/agenda/",
        }
        for ancien, attendu in cas.items():
            with self.subTest(ancien=ancien):
                response = self.client.get(ancien)
                self.assertEqual(response.status_code, 301)
                self.assertEqual(response["Location"], attendu)
        self.assertEqual(self.client.get("/fr-fr/rien-du-tout/").status_code, 404)
        self.assertEqual(self.client.get("/fr-fr/documents/5/introuvable.pdf").status_code, 404)

    def test_old_blog_post_renamed_on_migration(self):
        self.assertEqual(self.client.get("/fr-fr/blog/sites-faciles/")["Location"], "/fr/blog/")  # billet absent ici : rubrique


class ReecrireLiensTests(Base):
    # (cible_blog importé ci-dessous)
    def test_links_to_old_site_and_ghost_are_rewritten_only_when_an_equivalent_exists(self):
        from django.core.management import call_command
        from io import StringIO
        from core.management.commands.reecrire_liens import cible_blog
        DirectoryEntry.objects.create(name="Carton Plein", slug="carton-plein")
        service = Service.objects.create(
            name="Test", slug="test-liens", summary="x",
            description='Voir [la fiche](https://old.lesgrandsvoisins.com/fr-fr/annuaire/carton-plein/) '
                        'et [les votes](https://old.lesgrandsvoisins.com/fr-fr/association/conseils-des-voisins/27/vote/).',
        )
        Tag.objects.create(name="Resdigita", slug="resdigita")
        service.description += " [étiquette](https://blog.lesgrandsvoisins.com/tag/resdigita/)"
        service.url = "https://old.lesgrandsvoisins.com/"  # un service qui désigne l'ancien site : intact
        service.save()
        out = StringIO()
        call_command("reecrire_liens", stdout=out)  # simulation : rien n'est écrit
        service.refresh_from_db()
        self.assertIn("old.lesgrandsvoisins.com/fr-fr/annuaire/carton-plein", service.description)
        call_command("reecrire_liens", "--appliquer", stdout=out)
        service.refresh_from_db()
        self.assertIn("(/fr/annuaire/carton-plein/)", service.description)
        self.assertIn("(/fr/etiquettes/resdigita/)", service.description)
        self.assertEqual(service.url, "https://old.lesgrandsvoisins.com/")
        self.assertEqual(cible_blog("/tag/inconnue/"), "/fr/recherche/?q=inconnue")
        self.assertIn("https://old.lesgrandsvoisins.com/fr-fr/association/conseils-des-voisins/27/vote/", service.description)
        self.assertIn("conseils-des-voisins/27/vote/", out.getvalue())  # signalé comme sans équivalent
        # Réparation de liens écrits avec l'hôte du site Wagtail : rendus relatifs.
        service.description = "[x](https://www.lesgrandsvoisins.fr/fr/blog/un-billet/) [y](https://www.lesgrandsvoisins.fr/ailleurs/)"
        service.save()
        call_command("reecrire_liens", "--appliquer", "--reparer-hote", "www.lesgrandsvoisins.fr", stdout=out)
        service.refresh_from_db()
        self.assertIn("(/fr/blog/un-billet/)", service.description)
        self.assertIn("https://www.lesgrandsvoisins.fr/ailleurs/", service.description)  # hors chemins d'ici : intact


class RedirectionCourrierTests(Base):
    """Redirection de courrier : annuaire LDAP simulé (ldap3 MOCK_SYNC), aucun accès réel."""
    ADRESSES = ["duponlucie@gv.je", "duponlucie@lesgrandsvoisins.com"]

    def setUp(self):
        super().setUp()
        import tempfile
        from ldap3 import MOCK_SYNC, Connection, Server
        self.override = override_settings(REDIRECTIONS_ENABLED=True)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dn = "cn=duponlucie@gv.je,ou=users,dc=lesgrandsvoisins,dc=com"
        self.conn = Connection(Server("fake"), user="cn=x", password="x", client_strategy=MOCK_SYNC)
        self.conn.strategy.add_entry(self.dn, {
            "objectClass": ["inetOrgPerson", "inetLocalMailRecipient"], "cn": "duponlucie@gv.je", "sn": "Dupont",
            "mail": self.ADRESSES, "userPassword": "x",
        })
        self.conn.bind()
        patcher = mock.patch("core.redirections._connection", side_effect=lambda: (self.conn.bind(), self.conn)[1])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = get_user_model().objects.create_user("sub-lucie")
        self.client.force_login(self.user)
        from .auth import LOGIN_IDENTIFIER_KEY, MAIL_ADDRESSES_KEY
        session = self.client.session
        session[MAIL_ADDRESSES_KEY] = self.ADRESSES
        session[LOGIN_IDENTIFIER_KEY] = "duponlucie@gv.je"
        session.save()
        self.url = reverse("core:redirection_courrier")

    def attrs(self):
        self.conn.bind()  # le code testé se déconnecte après chaque usage
        self.conn.search(self.dn, "(objectClass=*)", search_scope="BASE", attributes=["mailRoutingAddress", "mailLocalAddress"])
        e = self.conn.entries[0]
        return (e.mailRoutingAddress.values if "mailRoutingAddress" in e else [],
                e.mailLocalAddress.values if "mailLocalAddress" in e else [])

    def demander(self, cible="lucie@exemple.org", copie=True):
        data = {"action": "demander", "cible": cible}
        if copie:
            data["copie"] = "on"
        return self.client.post(self.url, data)

    def lien(self):
        return re.search(r"https?://\S+/confirmer/\S+/", mail.outbox[-1].body).group(0)

    def test_disabled_by_default(self):
        with override_settings(REDIRECTIONS_ENABLED=False):
            self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_refused_targets_send_nothing(self):
        for cible in ["pas une adresse", "x@gv.je", "x@sous.lesgrandsvoisins.com", "duponlucie@gv.je", "postmaster@exemple.org"]:
            with self.subTest(cible=cible):
                self.demander(cible)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.attrs(), ([], []))

    def test_request_confirm_then_directory_is_written(self):
        self.demander()
        self.assertEqual(mail.outbox[-1].to, ["lucie@exemple.org"])
        self.assertEqual(self.attrs(), ([], []))  # rien dans l'annuaire avant confirmation
        lien = self.lien()
        from .models import RedirectionRequest
        token = lien.rstrip("/").rsplit("/", 1)[1]
        self.assertNotEqual(RedirectionRequest.objects.get().token_digest, token)  # seul le condensé est conservé
        self.client.logout()  # la personne qui confirme n'est pas connectée
        self.assertEqual(self.client.get(lien).status_code, 200)
        self.assertEqual(self.attrs(), ([], []))  # un simple GET (antivirus) ne confirme rien
        self.assertEqual(self.client.post(lien).status_code, 200)
        self.assertEqual(self.attrs(), (["lucie@exemple.org"], ["duponlucie@gv.je"]))
        self.assertEqual(self.client.get(lien).status_code, 404)  # usage unique

    def test_without_copy_and_toggle_copy_and_disable(self):
        self.demander(copie=False)
        self.client.post(self.lien())
        self.assertEqual(self.attrs(), (["lucie@exemple.org"], []))
        self.client.force_login(self.user)
        self.client.post(self.url, {"action": "copie", "copie": "on"})
        self.assertEqual(self.attrs(), (["lucie@exemple.org"], ["duponlucie@gv.je"]))
        self.client.post(self.url, {"action": "desactiver"})
        self.assertEqual(self.attrs(), ([], []))
        self.assertContains(self.client.get(self.url), "Aucune redirection active")

    def test_displayed_target_is_masked(self):
        self.demander()
        self.client.post(self.lien())
        self.client.force_login(self.user)
        page = self.client.get(self.url)
        self.assertContains(page, "l***@exemple.org")
        self.assertNotContains(page, "lucie@exemple.org")

    def test_expired_token_is_refused(self):
        from datetime import timedelta
        from .models import RedirectionRequest
        self.demander()
        RedirectionRequest.objects.update(expires=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.client.get(self.lien()).status_code, 404)

    def test_rate_limits(self):
        for i in range(5):
            self.demander(f"a{i}@exemple.org")
        self.assertEqual(len(mail.outbox), 5)
        self.demander("autre@exemple.org")  # 6e demande du jour pour ce membre
        self.assertEqual(len(mail.outbox), 5)

    def test_per_target_limit(self):
        for _ in range(3):
            self.demander("meme@exemple.org")
        self.demander("meme@exemple.org")
        self.assertEqual(len(mail.outbox), 3)

    def test_managed_by_admin_cannot_be_changed(self):
        statiques = f"{self.tmp.name}/statiques.txt"
        open(statiques, "w").write("# redirections statiques\nDuponLucie@gv.je\n")
        with override_settings(REDIRECTIONS_STATIC_FILE=statiques):
            self.assertContains(self.client.get(self.url), "gérée par l'administration")
            self.demander()
        self.assertEqual(len(mail.outbox), 0)

    def test_ambiguous_or_missing_mailbox_is_refused_without_writing(self):
        self.demander()
        self.conn.strategy.add_entry("cn=autre,ou=users,dc=lesgrandsvoisins,dc=com", {
            "objectClass": ["inetOrgPerson", "inetLocalMailRecipient"], "cn": "autre", "sn": "A", "mail": ["duponlucie@gv.je"]})
        self.client.logout()
        response = self.client.post(self.lien())
        self.assertEqual(response.status_code, 503)  # deux entrées : refus
        self.assertEqual(self.attrs(), ([], []))

    def test_audit_never_contains_the_target(self):
        from .models import RedirectionAudit
        self.demander()
        self.assertEqual(list(RedirectionAudit.objects.values_list("action", flat=True)), ["demande"])


class InventaireContenuTests(Base):
    def test_inventory_lists_content_with_alerts(self):
        import csv as _csv
        import tempfile
        from pathlib import Path
        from django.core.management import call_command
        DirectoryEntry.objects.create(name="Fiche courte", slug="fiche-courte")
        with tempfile.TemporaryDirectory() as d:
            call_command("inventaire_contenu", "--sortie", d, stdout=__import__("io").StringIO())
            lignes = list(_csv.DictReader(open(Path(d) / "inventaire.csv", encoding="utf-8-sig")))
            self.assertTrue((Path(d) / "resume.md").exists())
        types = {l["type"] for l in lignes}
        self.assertIn("Service", types)
        fiche = next(l for l in lignes if l["titre"] == "Fiche courte")
        self.assertIn("non-publique", fiche["alertes"])
        self.assertEqual(fiche["décision"], "")


class DeconnexionKeycloakTests(Base):
    """Déconnexion unique (RP-initiated logout) : adresse construite, id_token, repli, réglage, session locale effacée."""
    ENDPOINT = "https://key.example/realms/master/protocol/openid-connect/logout"

    def setUp(self):
        super().setUp()
        self.o = override_settings(KEYCLOAK_REALM_URL="https://key.example/realms/master", OIDC_RP_CLIENT_ID="voisinternet",
                                   DECONNEXION_KEYCLOAK=True, ALLOWED_HOSTS=["www.lesgrandsvoisins.com", "testserver"])
        self.o.enable()
        self.addCleanup(self.o.disable)
        patcher = mock.patch("core.auth.urlopen", side_effect=OSError("découverte injoignable"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def requete(self, id_token=None):
        from django.test import RequestFactory
        from django.contrib.sessions.backends.db import SessionStore
        r = RequestFactory().get("/", HTTP_HOST="www.lesgrandsvoisins.com", secure=True)
        r.session = SessionStore()
        if id_token:
            r.session["oidc_id_token"] = id_token
        return r

    def test_url_with_id_token_hint(self):
        from urllib.parse import parse_qs, urlsplit
        from .auth import keycloak_logout_url
        url = keycloak_logout_url(self.requete("tok.en.secret"))
        parts = urlsplit(url)
        self.assertEqual(f"{parts.scheme}://{parts.netloc}{parts.path}", self.ENDPOINT)
        q = parse_qs(parts.query)
        self.assertEqual(q["id_token_hint"], ["tok.en.secret"])
        self.assertTrue(q["post_logout_redirect_uri"][0].startswith("https://www.lesgrandsvoisins.com/"))
        self.assertNotIn("client_id", q)

    def test_fallback_without_id_token(self):
        from urllib.parse import parse_qs, urlsplit
        from .auth import keycloak_logout_url
        q = parse_qs(urlsplit(keycloak_logout_url(self.requete())).query)
        self.assertEqual(q["client_id"], ["voisinternet"])
        self.assertNotIn("id_token_hint", q)

    def test_parameters_are_encoded(self):
        from .auth import keycloak_logout_url
        url = keycloak_logout_url(self.requete("a b&c=d"))
        self.assertIn("id_token_hint=a+b%26c%3Dd", url)

    def test_discovery_end_session_endpoint_is_used_when_available(self):
        import io
        from .auth import keycloak_logout_url
        reponse = io.BytesIO(json.dumps({"end_session_endpoint": "https://key.example/autre/logout"}).encode())
        reponse.__enter__ = lambda s: s
        reponse.__exit__ = lambda *a: None
        with mock.patch("core.auth.urlopen", return_value=reponse):
            self.assertTrue(keycloak_logout_url(self.requete("t")).startswith("https://key.example/autre/logout?"))

    def test_setting_off_returns_home_without_touching_keycloak(self):
        from .auth import keycloak_logout_url
        with override_settings(DECONNEXION_KEYCLOAK=False):
            url = keycloak_logout_url(self.requete("tok"))
        self.assertTrue(url.startswith("https://www.lesgrandsvoisins.com/"))
        self.assertNotIn("tok", url)

    def test_logout_view_clears_local_session_and_redirects_to_keycloak(self):
        from mozilla_django_oidc.views import OIDCLogoutView
        user = get_user_model().objects.create_user("sub-x")
        r = self.requete("tok")
        r.method = "POST"
        r.user = user
        with override_settings(OIDC_OP_LOGOUT_URL_METHOD="core.auth.keycloak_logout_url"):
            reponse = OIDCLogoutView.as_view()(r)
        self.assertEqual(reponse.status_code, 302)
        self.assertTrue(reponse["Location"].startswith(self.ENDPOINT))
        self.assertIn("id_token_hint=tok", reponse["Location"])
        self.assertIsNone(r.session.get("oidc_id_token"))  # session locale effacée
