"""Page caching that is safe to apply to pages logged-in users also visit.

``@cache_page`` on its own would serve one visitor's rendered page to
everyone, and adding ``@vary_on_cookie`` fixes correctness but destroys the
hit rate (every session gets its own entry). Caching only the anonymous
response keeps both: bots and first-time visitors — the traffic that TTFB
actually matters for — hit the cache, and signed-in users always render fresh.

Invalidation is by *version*, not by key. Working out which URLs a saved
product appears on is intractable (its category page, page 3 of that listing,
the home page's featured row, a related-products block on a sibling product),
so instead every cached key is namespaced with a counter that any content save
bumps. Stale entries are never read again and expire on their own.
"""

from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

CONTENT_VERSION_KEY = 'seo:content-version'


def content_version():
    version = cache.get(CONTENT_VERSION_KEY)
    if version is None:
        version = 1
        cache.set(CONTENT_VERSION_KEY, version, None)
    return version


def bump_content_version():
    """Retire every cached page. Called from post_save/post_delete signals."""
    try:
        cache.incr(CONTENT_VERSION_KEY)
    except ValueError:
        # Key absent or expired — seeding it is equivalent to bumping, since
        # nothing cached under the previous namespace will be read again.
        cache.set(CONTENT_VERSION_KEY, content_version() + 1, None)


def cache_page_for_anonymous(timeout=None):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = getattr(request, 'user', None)
            if request.method not in ('GET', 'HEAD') or (user is not None and user.is_authenticated):
                return view_func(request, *args, **kwargs)

            ttl = timeout if timeout is not None else settings.SEO_PAGE_CACHE_SECONDS
            cached_view = cache_page(
                ttl, key_prefix=f'anon-v{content_version()}'
            )(view_func)
            return cached_view(request, *args, **kwargs)

        return wrapper

    return decorator


def cached_page_class(timeout=None):
    """Class-based-view form of :func:`cache_page_for_anonymous`."""
    return method_decorator(cache_page_for_anonymous(timeout), name='dispatch')


def versioned_cache_page(timeout):
    """``cache_page`` for views with no per-user variation (robots, sitemaps)."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            cached_view = cache_page(
                timeout, key_prefix=f'public-v{content_version()}'
            )(view_func)
            return cached_view(request, *args, **kwargs)

        return wrapper

    return decorator
