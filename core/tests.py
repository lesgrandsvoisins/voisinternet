from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .accounts import SESSION_KEY
from .models import Account, Audience, Donor, Service, Shortcut, format_number


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class Base(TestCase):
    fixtures = ["initial"]

    def setUp(self):
        cache.clear()
        self.service = Service.objects.get(slug="courriel")


class PagesTests(Base):
    def test_every_conjugated_page_renders(self):
        for name in ["home", "je_vois", "tu_vois", "il_ou_elle_voit", "nous_voyons",
                     "vous_voyez", "ils_et_elles_voient"]:
            with self.subTest(page=name):
                response = self.client.get(reverse(f"core:{name}"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Voyons")  # le menu conjugué est présent

    def test_header_says_se_connecter_for_new_visitor(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Je vois : se connecter")

    def test_header_widget_lists_keycloak_actions_and_shortcuts(self):
        self.client.post(reverse("core:toggle_shortcut", args=["courriel"]))
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Se connecter")
        self.assertContains(response, "Créer un compte")
        self.assertContains(response, self.service.name)

    def test_current_page_is_marked(self):
        response = self.client.get(reverse("core:vous_voyez"))
        self.assertContains(response, 'aria-current="page"')


class AnonymousAccountTests(Base):
    def test_adding_a_service_creates_an_anonymous_account(self):
        response = self.client.post(reverse("core:toggle_shortcut", args=["courriel"]))
        self.assertRedirects(response, reverse("core:je_vois"), fetch_redirect_response=False)
        account = Account.objects.get()
        self.assertTrue(account.is_anonymous_only)
        self.assertTrue(Shortcut.objects.filter(account=account, service=self.service).exists())
        # Le numéro est montré une seule fois, puis oublié.
        page = self.client.get(reverse("core:je_vois"))
        self.assertContains(page, "Votre numéro de compte")
        again = self.client.get(reverse("core:je_vois"))
        self.assertNotContains(again, "Votre numéro de compte")

    def test_number_is_never_stored_in_clear(self):
        account, digits = Account.create_anonymous()
        self.assertNotIn(digits, account.number_digest)
        self.assertEqual(len(account.number_digest), 64)

    def test_recover_with_number(self):
        account, digits = Account.create_anonymous()
        Shortcut.objects.create(account=account, service=self.service)
        response = self.client.post(reverse("core:recover_anonymous"), {"number": format_number(digits)})
        self.assertRedirects(response, reverse("core:je_vois"))
        self.assertEqual(self.client.session[SESSION_KEY], account.pk)
        self.assertContains(self.client.get(reverse("core:home")), "mes raccourcis (1)")

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
        self.assertEqual(ordered, ["agenda", "courriel"])
        self.assertEqual(first.service.name, "Courriel")
        self.assertEqual(second.service.name, "Agenda")

    def test_shortcuts_reorder_via_personal_action(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user("user")
        account = Account.objects.create(user=user)
        service_two = Service.objects.create(name="Agenda", slug="agenda", summary="Agenda personnel.")
        first = Shortcut.objects.create(account=account, service=self.service, position=10)
        second = Shortcut.objects.create(account=account, service=service_two, position=20)

        self.client.force_login(user)
        response = self.client.post(reverse("core:reorder_shortcut", args=[self.service.slug, "down"]))
        self.assertRedirects(response, reverse("core:je_vois"), fetch_redirect_response=False)
        ordered = list(account.shortcut_set.order_by("position").values_list("service__slug", flat=True))
        self.assertEqual(ordered, ["agenda", "courriel"])
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.position, 20)
        self.assertEqual(second.position, 10)

    def test_htmx_reorder_returns_partial_without_full_reload(self):
        from django.contrib.auth import get_user_model

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

    def test_htmx_toggle_returns_partial_with_out_of_band_updates(self):
        response = self.client.post(reverse("core:toggle_shortcut", args=["courriel"]), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-pressed="true"')
        self.assertContains(response, 'id="account"')
        self.assertContains(response, "hx-swap-oob")
        self.assertContains(response, "Notez votre numéro")
        # Deuxième clic : retrait, pas de nouveau compte.
        self.client.post(reverse("core:toggle_shortcut", args=["courriel"]), HTTP_HX_REQUEST="true")
        self.assertEqual(Account.objects.count(), 1)
        self.assertEqual(Shortcut.objects.count(), 0)


class LinkingTests(Base):
    def test_anonymous_shortcuts_join_the_named_account(self):
        from django.contrib.auth import get_user_model
        self.client.post(reverse("core:toggle_shortcut", args=["courriel"]))
        user = get_user_model().objects.create_user("voisine")
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse("core:je_vois")), "Rattacher mes raccourcis")
        self.client.post(reverse("core:link_anonymous"))
        self.assertTrue(Shortcut.objects.filter(account__user=user, service=self.service).exists())
        self.assertFalse(Account.objects.filter(user__isnull=True).exists())


class DonorPrivacyTests(TestCase):
    def test_only_consenting_donors_are_listed(self):
        Donor.objects.create(name="Voisine généreuse", public=True)
        Donor.objects.create(name="Donateur discret", public=False)
        response = self.client.get(reverse("core:ils_et_elles_voient"))
        self.assertContains(response, "Voisine généreuse")
        self.assertNotContains(response, "Donateur discret")


class AudienceTests(Base):
    def test_home_asks_who_you_are(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Vous êtes…")
        self.assertContains(response, reverse("core:vous_voyez_pour", args=["associations"]))

    def test_audience_page_filters_services(self):
        pros = Audience.objects.get(slug="artistes-et-artisans")
        vitrine = Service.objects.create(name="Vitrine pro", slug="vitrine-pro", summary="Pour les pros.")
        vitrine.audiences.add(pros)
        mine = self.client.get(reverse("core:vous_voyez_pour", args=["artistes-et-artisans"]))
        self.assertContains(mine, "Vitrine pro")
        self.assertContains(mine, "Courriel")  # sans public désigné : pour tout le monde
        other = self.client.get(reverse("core:vous_voyez_pour", args=["associations"]))
        self.assertNotContains(other, "Vitrine pro")
        self.assertContains(mine, 'aria-current="page"')

    def test_partnership_audience_has_no_add_buttons(self):
        response = self.client.get(reverse("core:vous_voyez_pour", args=["mairies-et-institutions"]))
        self.assertContains(response, "Proposer un partenariat")
        self.assertNotContains(response, 'class="add"')

    def test_unknown_audience_is_404(self):
        self.assertEqual(self.client.get(reverse("core:vous_voyez_pour", args=["inconnu"])).status_code, 404)
