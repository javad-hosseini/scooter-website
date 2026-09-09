# apps/shop/signals.py
"""
Cache-invalidation signals for the shop app.

Every time a Product or Category is saved or deleted the anonymous page cache
is retired via bump_content_version().  This keeps the version-based cache
strategy in apps/seo/cache.py working without having to enumerate individual
URL keys (which is intractable given how many listing pages a single product
can appear on).
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.seo.cache import bump_content_version


@receiver([post_save, post_delete], sender='shop.Product')
def _invalidate_cache_on_product_change(sender, **kwargs):
    """پس از ذخیره یا حذف هر محصول، نسخه کش صفحات ابطال می‌شود."""
    bump_content_version()


@receiver([post_save, post_delete], sender='shop.Category')
def _invalidate_cache_on_category_change(sender, **kwargs):
    """پس از ذخیره یا حذف هر دسته‌بندی، نسخه کش صفحات ابطال می‌شود."""
    bump_content_version()
