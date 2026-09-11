from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .accounts import SESSION_KEY
from .models import Account, Donor, Service, Shortcut, format_number


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
