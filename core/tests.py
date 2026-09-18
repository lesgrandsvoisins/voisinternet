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
from django.utils import timezone

from cms.models import Author, AuthorMessage, ContentPage, PolePage
from cms.qmd import export_contentpage_qmd, import_contentpage_qmd

from .accounts import SESSION_KEY
from .models import (
    Account, Audience, Contribution, DirectoryEntry, DirectorySector, Donor, EntryMessage, EntrySubscription,
    Event, EventInterest, EventManagementRequest, Membership, OwnershipClaim, Service, Shortcut, Tag, format_number,
)


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
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

    def test_wagtail_pages_render(self):
        # Pages gérées par Wagtail (cms.PolePage, ContactPage, AssociationPage,
        # DonationPage) : pas de nom d'URL Django à inverser (voir core/menu.py).
        for path in ["/fr/civisme/", "/fr/arts-plastiques/", "/fr/numerique/",
                     "/fr/contact/", "/fr/grandsvoisins/", "/fr/contributions/"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="main-menu-panel"')

    def test_header_says_se_connecter_for_new_visitor(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Connecter")

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
        self.assertNotIn("Mes raccourcis", panel)


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


class AnonymousAccountTests(Base):
    def test_adding_a_service_creates_an_anonymous_account(self):
        response = self.client.post(reverse("core:toggle_shortcut", args=[self.service.slug]))
        self.assertRedirects(response, reverse("core:account"), fetch_redirect_response=False)
        account = Account.objects.get()
        self.assertTrue(account.is_anonymous_only)
        self.assertTrue(Shortcut.objects.filter(account=account, service=self.service).exists())
        # Le numéro est montré une seule fois, puis oublié.
        page = self.client.get(reverse("core:account"))
        self.assertContains(page, "Votre numéro de compte")
        again = self.client.get(reverse("core:account"))
        self.assertNotContains(again, "Votre numéro de compte")

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
        self.assertContains(self.client.get(reverse("core:account")), "Rattacher mes raccourcis")
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
        self.assertRedirects(response, reverse("core:mes_evenements"))
        event = Event.objects.get(title="Atelier vélo")
        self.assertFalse(event.public)
        acc = Account.objects.get(user=user)
        self.assertIn(event, acc.managed_events.all())

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
        self.assertRedirects(response, "/en/agenda/mes-evenements/")
        event = Event.objects.get(title_en="Bike workshop")
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
        self.assertRedirects(response, reverse("core:mes_evenements"))
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
            "sender_name": "Alice", "sender_email": "alice@example.org", "message": "Bonjour !", "website": "",
        })
        self.assertRedirects(response, reverse("core:author_detail", args=[self.author.pk]))
        self.assertEqual(AuthorMessage.objects.filter(author=self.author).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["jean@example.org"])
        self.assertEqual(mail.outbox[0].reply_to, ["alice@example.org"])

    def test_honeypot_silently_drops_message(self):
        self.client.post(reverse("core:author_detail", args=[self.author.pk]), {
            "sender_name": "Robot", "sender_email": "bot@example.org", "message": "spam",
            "website": "http://spam.example",
        })
        self.assertEqual(AuthorMessage.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_contact_form_is_throttled(self):
        for _ in range(5):
            self.client.post(reverse("core:author_detail", args=[self.author.pk]), {
                "sender_name": "Alice", "sender_email": "alice@example.org", "message": "Bonjour !", "website": "",
            })
        self.assertEqual(len(mail.outbox), 5)
        response = self.client.post(reverse("core:author_detail", args=[self.author.pk]), {
            "sender_name": "Alice", "sender_email": "alice@example.org", "message": "Encore un.", "website": "",
        }, follow=True)
        self.assertEqual(len(mail.outbox), 5)  # le 6e message n'est pas parti
        self.assertContains(response, "Trop de messages envoyés récemment")


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
            "sender_name": "Alice", "sender_email": "alice@example.org", "message": "Bonjour !", "website": "",
        })
        self.assertRedirects(response, reverse("core:entry_detail", args=[self.entry.slug]))
        self.assertEqual(EntryMessage.objects.filter(entry=self.entry).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["fiche@example.org"])
        self.assertEqual(mail.outbox[0].reply_to, ["alice@example.org"])

    def test_honeypot_silently_drops_message(self):
        self.client.post(reverse("core:entry_detail", args=[self.entry.slug]), {
            "sender_name": "Robot", "sender_email": "bot@example.org", "message": "spam",
            "website": "http://spam.example",
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
