"""Helpers shared by every page that needs canonical URLs or meta text."""

import re

from django.conf import settings
from django.utils.html import strip_tags
from django.utils.text import Truncator

_WHITESPACE = re.compile(r'\s+')

#: Google truncates descriptions around 155-160 characters on desktop.
META_DESCRIPTION_LENGTH = 158
#: Titles are truncated around 60 characters including the brand suffix.
META_TITLE_LENGTH = 60


def site_origin(request=None):
    """Return the canonical ``scheme://host`` for this site, without a trailing slash.

    ``SITE_URL`` wins when configured so that canonical tags stay stable even
    when the app is reached over an internal hostname or an IP address. It
    falls back to the request when unset, which keeps local development and
    staging working without extra configuration.
    """
    if settings.SITE_URL:
        return settings.SITE_URL.rstrip('/')
    if request is not None:
        return f'{request.scheme}://{request.get_host()}'
    return ''


def absolute_url(path, request=None):
    """Turn ``/shop/product/x/`` (or an already-absolute URL) into a full URL."""
    if not path:
        return ''
    if path.startswith(('http://', 'https://', '//')):
        return path
    origin = site_origin(request)
    if not path.startswith('/'):
        path = '/' + path
    return f'{origin}{path}'


def canonical_url(request, path=None):
    """Self-referencing canonical for the current page.

    Deliberately drops the query string: ``?page=2`` is handled explicitly by
    the paginated views, and every other parameter (filters, sorts, tracking
    tags) must fold back into the clean URL rather than spawning a duplicate.
    """
    return absolute_url(path if path is not None else request.path, request)


def clean_text(value):
    """Strip markup and collapse whitespace so meta text is single-line plain text."""
    if not value:
        return ''
    return _WHITESPACE.sub(' ', strip_tags(str(value))).strip()


def meta_description(*candidates, length=META_DESCRIPTION_LENGTH):
    """Return the first non-empty candidate, cleaned and truncated on a word boundary."""
    for candidate in candidates:
        text = clean_text(candidate)
        if text:
            return Truncator(text).chars(length, truncate='…')
    return ''


def meta_title(title, brand=None, separator=' | ', length=META_TITLE_LENGTH):
    """Build ``<page title> | <brand>`` and keep it inside the SERP display limit.

    The brand suffix is preserved and the page-specific part is shortened,
    because losing the brand hurts recognisability more than losing a few
    trailing words of the title.
    """
    title = clean_text(title)
    brand = brand if brand is not None else settings.SITE_NAME
    if not brand:
        return Truncator(title).chars(length, truncate='…')
    suffix = f'{separator}{brand}'
    room = length - len(suffix)
    if room < 15:  # brand alone is already long; don't mangle the title
        return f'{title}{suffix}'
    if len(title) > room:
        title = Truncator(title).chars(room, truncate='…')
    return f'{title}{suffix}'


def image_url(image_field, request=None, fallback=None):
    """Absolute URL for an ImageField, falling back to a static asset."""
    if image_field:
        try:
            return absolute_url(image_field.url, request)
        except ValueError:
            pass
    if fallback:
        return absolute_url(fallback, request)
    return ''
