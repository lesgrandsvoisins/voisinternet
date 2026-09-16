from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0023_backfill_blogpostpage_author"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="blogpostpage",
            name="author_name",
        ),
    ]
