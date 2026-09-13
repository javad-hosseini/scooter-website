"""
Custom template tags and filters for shop and price formatting.
"""

from django import template

register = template.Library()


@register.filter(name='intcomma')
def intcomma(value):
    """
    Format a number with commas grouping digits 3-by-3 from the right.
    Handles None, empty string, int, float, and Decimal.
    e.g. 89000000 -> 89,000,000
    """
    if value is None or value == '':
        return ''
    try:
        val = int(round(float(value)))
        return f"{val:,}"
    except (ValueError, TypeError):
        return str(value)


@register.filter(name='persian_intcomma')
def persian_intcomma(value):
    """
    Format a number with 3-digit comma separation and convert digits to Persian.
    e.g. 89000000 -> ۸۹,۰۰۰,۰۰۰
    """
    formatted = intcomma(value)
    if not formatted:
        return ''
    persian_digits = {
        '0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴',
        '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹'
    }
    return ''.join(persian_digits.get(ch, ch) for ch in formatted)


@register.filter(name='format_price')
def format_price(value):
    """
    Alias for intcomma.
    e.g. 89000000 -> 89,000,000
    """
    return intcomma(value)
