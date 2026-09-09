"""Retire cached pages whenever indexable content changes.

Without this, editing a price or publishing an article would leave the old
page being served — to shoppers and to crawlers — for up to
``SEO_PAGE_CACHE_SECONDS``, and the sitemap for up to a day.
"""

from django.apps import apps
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache import bump_content_version

#: ``app_label.ModelName`` for everything that appears on a cached page.
WATCHED_MODELS = [
    'shop.Product',
    'shop.Category',
    'shop.ProductImage',
    'shop.ProductSpec',
    'shop.ProductReview',
    'shop.CategoryHeroProduct',
    'home.Article',
    'home.Tag',
    'home.IndexPageSettings',
    'home.ProductCard',
    'home.Testimonial',
    'home.Promise',
    'home.CategoryFeature',
]


def _invalidate(sender, **kwargs):
    bump_content_version()


def connect():
    for label in WATCHED_MODELS:
        try:
            model = apps.get_model(label)
        except LookupError:  # pragma: no cover - guards against renames
            continue
        post_save.connect(_invalidate, sender=model, dispatch_uid=f'seo-save-{label}')
        post_delete.connect(_invalidate, sender=model, dispatch_uid=f'seo-del-{label}')
