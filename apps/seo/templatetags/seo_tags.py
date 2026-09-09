import json

from django import template
from django.utils.safestring import mark_safe

from ..utils import absolute_url as _absolute_url
from ..utils import clean_text as _clean_text
from ..utils import meta_description as _meta_description

register = template.Library()


@register.filter
def json_ld(value):
    """Serialise a dict/list to JSON that is safe inside a <script> element.

    ``</script>`` inside any string value would otherwise close the block
    early, so the forward slash is escaped. ``ensure_ascii=False`` keeps
    Persian readable instead of exploding into \\uXXXX escapes.
    """
    if not value:
        return ''
    dumped = json.dumps(value, ensure_ascii=False, default=str)
    dumped = dumped.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return mark_safe(dumped)  # noqa: S308 - escaped above


@register.filter
def absolute_url(path, request=None):
    return _absolute_url(path, request)


@register.filter
def meta_text(value, length=158):
    """Strip markup and truncate for use in a meta description."""
    return _meta_description(value, length=int(length))


@register.filter
def plain(value):
    return _clean_text(value)


@register.simple_tag
def img_dimensions(image, fallback_width=1200, fallback_height=800):
    """``width``/``height`` attributes for an ImageField.

    Reserving the box before the image arrives is what stops the layout
    shifting; falling back to nominal dimensions keeps the aspect ratio
    roughly right for legacy rows whose size was never recorded.

    Dimensions come from the model's ``width_field``/``height_field`` columns
    when they are populated. ``image.width`` would be simpler, but it opens the
    file through Pillow on every access — 24 product cards on a listing page
    would mean 24 image decodes per request.
    """
    width = height = None

    if image:
        field = getattr(image, 'field', None)
        instance = getattr(image, 'instance', None)
        if field is not None and instance is not None and field.width_field:
            width = getattr(instance, field.width_field, None)
            height = getattr(instance, field.height_field, None)

        if not width or not height:
            # No cached dimensions (a row that predates the fields, or a
            # storage backend that could not measure the upload).
            try:
                width, height = image.width, image.height
            except (OSError, ValueError):
                width = height = None

    if not width or not height:
        width, height = fallback_width, fallback_height
    return mark_safe(f'width="{width}" height="{height}"')  # noqa: S308 - ints only
