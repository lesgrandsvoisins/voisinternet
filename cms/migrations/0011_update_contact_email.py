from django.db import migrations

# L'adresse de contact seedée par 0008_seed_more_pages (contact@voisinter.net)
# n'a pas suivi le passage du site à lesgrandsvoisins.com (cf. 0010).
OLD_EMAIL = "contact@voisinter.net"
NEW_EMAIL = "contact@lesgrandsvoisins.com"


def replace_email(page, card_title, old_email, new_email):
    from wagtail.rich_text import RichText

    for card in page.cards:
        if card.value["title"] == card_title:
            card.value["text"] = RichText(card.value["text"].source.replace(old_email, new_email))


def swap(old_email, new_email):
    from cms.models import ContactPage, DonationPage

    contact = ContactPage.objects.filter(slug="contact").first()
    if contact:
        replace_email(contact, "Par courriel", old_email, new_email)
        contact.save_revision().publish()

    donation = DonationPage.objects.filter(slug="contributions").first()
    if donation:
        replace_email(donation, "Donner du temps", old_email, new_email)
        donation.save_revision().publish()


def update_email(apps, schema_editor):
    swap(OLD_EMAIL, NEW_EMAIL)


def revert_email(apps, schema_editor):
    swap(NEW_EMAIL, OLD_EMAIL)


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0010_rename_voisinternet_to_domain"),
    ]

    operations = [
        migrations.RunPython(update_email, revert_email),
    ]
