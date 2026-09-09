"""A small value object every page fills in, plus the mixin that renders it.

Having one shape for page metadata is what makes it possible to render titles,
canonicals, Open Graph tags and JSON-LD from a single template include instead
of hand-writing them (inconsistently) in each of the site's templates.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from django.conf import settings
from django.templatetags.static import static

from .utils import absolute_url, canonical_url, meta_description, meta_title


@dataclass
class PageSEO:
    title: str = ''
    description: str = ''
    canonical: str = ''
    #: ``index,follow`` for real content; ``noindex,follow`` for filtered,
    #: searched, sorted or otherwise machine-generated views.
    robots: str = 'index, follow'
    og_type: str = 'website'
    image: str = ''
    image_alt: str = ''
    prev_url: str = ''
    next_url: str = ''
    published_time: Optional[Any] = None
    modified_time: Optional[Any] = None
    breadcrumbs: list = field(default_factory=list)
    json_ld: list = field(default_factory=list)

    def as_context(self):
        return {'seo': self}


class SEOMixin:
    """Adds a fully-populated ``seo`` object to the template context.

    Subclasses override :meth:`get_seo` (or the ``seo_*`` attributes) rather
    than editing ``<head>`` markup, so no template can drift out of sync.
    """

    seo_title = ''
    seo_description = ''
    seo_robots = 'index, follow'
    seo_og_type = 'website'
    #: Trail of ``(label, path)`` pairs; the last entry is the current page.
    breadcrumbs: list = []

    def get_breadcrumbs(self, context):
        return list(self.breadcrumbs)

    def get_seo_image(self, context):
        return ''

    def get_json_ld(self, context, seo):
        return []

    def get_canonical_path(self):
        return self.request.path

    def get_seo(self, context):
        request = self.request
        image = self.get_seo_image(context) or absolute_url(
            static(settings.SEO_DEFAULT_IMAGE), request
        )
        seo = PageSEO(
            title=meta_title(self.seo_title) if self.seo_title else settings.SEO_DEFAULT_TITLE,
            description=meta_description(
                self.seo_description, settings.SEO_DEFAULT_DESCRIPTION
            ),
            canonical=canonical_url(request, self.get_canonical_path()),
            robots=self.seo_robots,
            og_type=self.seo_og_type,
            image=image,
            breadcrumbs=self.get_breadcrumbs(context),
        )
        seo.json_ld = self.get_json_ld(context, seo)
        return seo

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['seo'] = self.get_seo(context)
        return context
