from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .accounts import SESSION_KEY
from .models import (
    Account, Audience, DirectoryEntry, DirectorySector, Donor, Event, Membership, Service, Shortcut, format_number,
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
            visibility=DirectoryEntry.VISIBILITY_PUBLIC,
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
            name="Ada Matus", slug="ada-matus", visibility=DirectoryEntry.VISIBILITY_PUBLIC,
        )
        response = self.client.get(reverse("core:annuaire"))
        self.assertContains(response, reverse("core:entry_detail", args=[entry.slug]))
