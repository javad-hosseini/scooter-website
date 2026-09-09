"""URL canonicalisation.

Django's ``CommonMiddleware`` already fixes missing trailing slashes. What it
does not fix is casing: ``/shop/product/NexGo-X100/`` and
``/shop/product/nexgo-x100/`` would both resolve on a case-sensitive lookup
only by accident, and any that do resolve serve the same content on two URLs.
Slugs are generated with ``slugify()``, which lowercases, so folding the path
to lowercase is always safe for content URLs.
"""

from django.conf import settings
from django.http import HttpResponsePermanentRedirect
from django.utils.deprecation import MiddlewareMixin

#: Paths whose casing is meaningful or externally owned.
EXEMPT_PREFIXES = (
    '/admin/',
    '/static/',
    '/media/',
    '/api/',
    '/i18n/',
    '/__debug__/',
)


class CanonicalUrlMiddleware(MiddlewareMixin):
    def process_request(self, request):
        path = request.path_info

        if request.method not in ('GET', 'HEAD'):
            return None
        if any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES):
            return None
        if '/api/' in path:
            return None

        lowered = path.lower()
        if lowered == path:
            return None

        # Only ASCII casing is folded; Persian slugs have no case and are
        # left byte-identical.
        new_url = request.build_absolute_uri(lowered)
        if request.META.get('QUERY_STRING'):
            new_url = f'{new_url}?{request.META["QUERY_STRING"]}'
        return HttpResponsePermanentRedirect(new_url)


class SEOHeadersMiddleware(MiddlewareMixin):
    """Cache-Control for HTML, plus ``X-Robots-Tag`` for non-HTML responses.

    Static assets are handled by WhiteNoise; this covers dynamic pages, where
    a short shared-cache TTL with ``stale-while-revalidate`` gives a CDN
    something to serve instantly without pinning stale prices in front of users.
    """

    def process_response(self, request, response):
        content_type = response.headers.get('Content-Type', '')

        # JSON/API responses stay crawlable (the pages hydrate from them) but
        # must never be indexed as documents in their own right.
        if 'X-Robots-Tag' not in response.headers and (
            content_type.startswith('application/json')
            or '/api/' in request.path_info
        ):
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'

        if response.streaming or response.status_code >= 400:
            return response
        if not content_type.startswith('text/html'):
            return response

        # Anything user-specific must never land in a shared cache.
        if getattr(request, 'user', None) is not None and request.user.is_authenticated:
            response.headers['Cache-Control'] = 'private, no-cache, no-store, max-age=0'
            return response
        if getattr(response, 'seo_no_cache', False):
            response.headers['Cache-Control'] = 'private, no-store'
            return response

        # Overwrites the plain "max-age=N" that @cache_page stamps on: that
        # would let *browsers* pin the page for the full TTL, so a shopper
        # would keep seeing an old price after a refresh. max-age=0 with
        # s-maxage moves the caching to the shared cache/CDN, where a purge
        # or a revalidation actually reaches everyone.
        ttl = settings.SEO_PAGE_CACHE_SECONDS
        response.headers['Cache-Control'] = (
            f'public, max-age=0, s-maxage={ttl}, stale-while-revalidate={ttl * 2}'
        )
        return response
