from django.conf import settings

from .utils import site_origin


def seo_defaults(request):
    """Site-wide values the head include and footer need on every page."""
    return {
        'SITE_NAME': settings.SITE_NAME,
        'SITE_ORIGIN': site_origin(request),
        'SITE_LOCALE': settings.SITE_LOCALE,
        'SEO_TWITTER_SITE': settings.SEO_TWITTER_SITE,
        'SEO_ORGANIZATION': settings.SEO_ORGANIZATION,
    }
