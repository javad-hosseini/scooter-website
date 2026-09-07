"""XML sitemaps.

Only canonical, indexable URLs belong here. Paginated pages past page 1,
faceted/sorted URLs, search results and account pages are all excluded — a
sitemap that lists URLs the site itself marks ``noindex`` sends contradictory
signals and wastes crawl budget.
"""

from django.contrib.sitemaps import Sitemap
from django.db.models import Max
from django.urls import reverse

from apps.home.models import Article
from apps.shop.models import Category, Product


class StaticViewSitemap(Sitemap):
    """Hand-maintained list of evergreen pages."""

    protocol = 'https'
    changefreq = 'monthly'

    #: ``(url name, priority, changefreq)``
    pages = [
        ('home_app:index', 1.0, 'daily'),
        ('shop:product_list', 0.9, 'daily'),
        ('home_app:articles', 0.7, 'weekly'),
        ('seo:about', 0.5, 'yearly'),
        ('seo:contact', 0.5, 'yearly'),
    ]

    def items(self):
        return self.pages

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):
        return item[1]

    def changefreq(self, item):  # noqa: A003 - name required by Django
        return item[2]


class ProductSitemap(Sitemap):
    protocol = 'https'
    changefreq = 'weekly'
    priority = 0.8
    limit = 25000

    def items(self):
        return (
            Product.objects.filter(is_published=True, is_discontinued=False)
            .only('slug', 'updated_at')
            .order_by('-updated_at')
        )

    def lastmod(self, obj):
        return obj.updated_at


class CategorySitemap(Sitemap):
    """Category landing pages — page 1 only, never ``?page=2`` and never filters."""

    protocol = 'https'
    changefreq = 'weekly'
    priority = 0.7
    limit = 25000

    def items(self):
        return (
            Category.objects.filter(is_active=True)
            .annotate(last_product_update=Max('products__updated_at'))
            .order_by('order', 'name')
        )

    def lastmod(self, obj):
        # A category is "modified" when its products change, which is the
        # signal that actually matters for recrawling a listing page.
        return obj.last_product_update or obj.updated_at


class ArticleSitemap(Sitemap):
    protocol = 'https'
    changefreq = 'monthly'
    priority = 0.6
    limit = 25000

    def items(self):
        return (
            Article.objects.filter(is_published=True)
            .only('slug', 'updated_at')
            .order_by('-published_at', '-created_at')
        )

    def lastmod(self, obj):
        return obj.updated_at


#: Registered with ``django.contrib.sitemaps.views``. Each key becomes a
#: section in the sitemap index (/sitemap.xml -> /sitemap-products.xml, ...),
#: and Django splits any section past ``limit`` URLs into ``?p=N`` pages
#: automatically, so this scales past the 50,000-URL protocol cap.
SITEMAPS = {
    'static': StaticViewSitemap,
    'categories': CategorySitemap,
    'products': ProductSitemap,
    'articles': ArticleSitemap,
}
