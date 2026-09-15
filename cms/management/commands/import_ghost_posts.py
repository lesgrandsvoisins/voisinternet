"""
Importe les articles exportés de l'ancien blog Ghost (deploy/ghost-export/*.md,
accompagnés de deploy/ghost-export/blog.json pour les auteurs) comme autant de
BlogPostPage, sous la page d'index créée par cms.migrations.0013_seed_blog_index.

Idempotent : un article déjà importé (même slug) est laissé tel quel.
"""
import json
import re
import shutil
from pathlib import Path

from django.conf import settings
from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from cms.models import BlogIndexPage, BlogPostPage
from core.templatetags.markdown_filters import markdown_filter

EXPORT_DIR = Path(settings.BASE_DIR) / "deploy" / "ghost-export"
MEDIA_SUBDIR = "ghost-import"


def parse_frontmatter(text):
    """
    Un analyseur volontairement minimal, pas un YAML complet : le frontmatter de
    cet export n'a que des paires « clé: valeur » sur une ligne, à une exception
    près — `excerpt: |` suivi d'un bloc indenté de deux espaces (voir
    deploy/ghost-export/fix_excerpt.py, qui a mis tous les fichiers dans cette forme).
    """
    lines = text.split("\n")
    end = lines.index("---", 1)
    fm_lines = lines[1:end]
    body = "\n".join(lines[end + 1:]).lstrip("\n")

    data = {}
    i = 0
    while i < len(fm_lines):
        line = fm_lines[i]
        if not line.strip():
            i += 1
            continue
        key, _, rest = line.partition(":")
        rest = rest.strip()
        if rest == "|":
            block = []
            i += 1
            while i < len(fm_lines) and (fm_lines[i].startswith("  ") or not fm_lines[i].strip()):
                block.append(fm_lines[i][2:] if fm_lines[i].startswith("  ") else "")
                i += 1
            data[key] = "\n".join(block).rstrip("\n")
            continue
        data[key] = rest
        i += 1
    return data, body


def make_excerpt(frontmatter):
    custom = frontmatter.get("custom_excerpt", "null")
    if custom and custom != "null":
        return custom[:300]
    excerpt = frontmatter.get("excerpt", "")
    first_para = excerpt.split("\n\n", 1)[0].replace("\n", " ").strip()
    return first_para[:300]


def rewrite_media_paths(html):
    media_url = settings.MEDIA_URL.rstrip("/")
    html = html.replace('src="./images/', f'src="{media_url}/{MEDIA_SUBDIR}/images/')
    html = html.replace('href="./files/', f'href="{media_url}/{MEDIA_SUBDIR}/files/')
    return html


class Command(BaseCommand):
    help = "Importe les articles de l'export Ghost (deploy/ghost-export) dans le blog Wagtail."

    def handle(self, *args, **options):
        self.copy_media()
        authors_by_post_id, users_by_id = self.load_authors()
        blog_index = BlogIndexPage.objects.get(slug="blog")

        created, skipped = 0, 0
        for path in sorted(EXPORT_DIR.glob("*.md")):
            frontmatter, body_md = parse_frontmatter(path.read_text(encoding="utf-8"))
            slug = frontmatter["slug"]
            if BlogPostPage.objects.filter(slug=slug).exists():
                skipped += 1
                continue

            author_ids = authors_by_post_id.get(frontmatter.get("ghost_id"), [])
            author_name = ", ".join(users_by_id[a] for a in author_ids if a in users_by_id)

            page = BlogPostPage(
                title=frontmatter["title"],
                draft_title=frontmatter["title"],
                slug=slug,
                date=parse_datetime(frontmatter["published_at"]),
                author_name=author_name,
                excerpt=make_excerpt(frontmatter),
                featured_image=self.get_featured_image(frontmatter.get("featured_image", "")),
                body=rewrite_media_paths(markdown_filter(body_md)),
            )
            blog_index.add_child(instance=page)
            page.save_revision().publish()
            created += 1
            self.stdout.write(f"importé : {slug}")

        self.stdout.write(self.style.SUCCESS(f"{created} article(s) importé(s), {skipped} déjà présent(s)."))

    def copy_media(self):
        dest_root = Path(settings.MEDIA_ROOT) / MEDIA_SUBDIR
        for sub in ("images", "files"):
            src = EXPORT_DIR / sub
            if src.is_dir():
                shutil.copytree(src, dest_root / sub, dirs_exist_ok=True)

    def load_authors(self):
        data = json.loads((EXPORT_DIR / "blog.json").read_text(encoding="utf-8"))["db"][0]["data"]
        users_by_id = {u["id"]: u["name"] for u in data["users"]}
        authors_by_post_id = {}
        for pa in data["posts_authors"]:
            authors_by_post_id.setdefault(pa["post_id"], []).append(pa["author_id"])
        return authors_by_post_id, users_by_id

    def get_featured_image(self, relative_path):
        if not relative_path:
            return None
        image_path = EXPORT_DIR / re.sub(r"^\./", "", relative_path)
        if not image_path.is_file():
            return None

        from wagtail.images.models import Image

        existing = Image.objects.filter(title=image_path.name).first()
        if existing:
            return existing
        try:
            with open(image_path, "rb") as f:
                return Image.objects.create(title=image_path.name, file=ImageFile(f, name=image_path.name))
        except Exception as exc:
            # Un fichier illisible (export corrompu) ne doit pas bloquer tout l'import :
            # l'article s'importe sans image de une.
            self.stderr.write(f"image ignorée ({image_path.name}) : {exc}")
            return None
