"""
Flux RSS du blog (cms.BlogPostPage), dans la langue du préfixe de l'adresse : /fr/blog/rss/, /en/blog/rss/…
Remplace le flux que servait l'ancien blog Ghost (blog.lesgrandsvoisins.com/rss/). Les adresses des articles sont bâties à partir de
l'hôte de la requête et du chemin RELATIF de la page (core.legacy.chemin_page) : `page.url` renvoie l'hôte du site Wagtail, pas forcément
celui d'ici.
"""
from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Rss201rev2Feed
from django.utils.html import strip_tags
from django.utils.translation import get_language, gettext as _
from wagtail.models import Locale

from .legacy import chemin_page


class FluxBlog(Feed):
    feed_type = Rss201rev2Feed

    def get_object(self, request, *args, **kwargs):
        self.request = request
        return None

    def title(self, obj):
        return _("Le blog des Grands Voisins")

    def description(self, obj):
        return _("Les derniers articles du blog des Grands Voisins.")

    def link(self):
        return self.request.build_absolute_uri(f"/{get_language()}/blog/")

    def items(self, obj):
        from cms.models import BlogPostPage

        langue = Locale.objects.filter(language_code=get_language()).first()
        articles = BlogPostPage.objects.live().public().select_related("author")
        if langue is not None:
            articles = articles.filter(locale=langue)
        return articles.order_by("-date")[:30]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.excerpt or strip_tags(item.body or "")[:300]

    def item_link(self, item):
        return self.request.build_absolute_uri(chemin_page(item) or f"/{get_language()}/blog/")

    def item_pubdate(self, item):
        return item.date

    def item_author_name(self, item):
        return item.author.name if item.author_id else None

    def item_categories(self, item):
        return [t.name for t in item.tags.all()]
