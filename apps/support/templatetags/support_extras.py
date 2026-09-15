"""
Template filters for the support app.

Responsibility:
    Exposes Jalali date formatting and Persian digit conversion
    as Django template filters for support templates.
"""

from django import template

from apps.support.utils import format_jalali_date, to_persian_digits

register = template.Library()


@register.filter(name="jalali_date")
def jalali_date(value):
    """Format a Gregorian datetime as a Persian (Jalali) date string."""
    return format_jalali_date(value)


@register.filter(name="jalali_datetime")
def jalali_datetime(value):
    """Format a Gregorian datetime as Persian date with time."""
    return format_jalali_date(value, include_time=True)


@register.filter(name="persian_digits")
def persian_digits(value):
    """Convert Western digits in a value to Persian digits."""
    return to_persian_digits(value)