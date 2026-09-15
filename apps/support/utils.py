"""
Presentation-layer helpers for the support app.

Responsibility:
    Converts Gregorian datetimes into human-readable Jalali (Persian)
    date strings with Persian digits for display in templates and admin.

Architectural decision:
    This conversion is intentionally kept out of the models and database.
    The DB stores Gregorian DateTimeField values; Jalali display is
    computed on demand wherever needed.
"""

import jdatetime

# Persian month names, in order (index 0 = فروردین).
PERSIAN_MONTH_NAMES = [
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
]

# Translation table for Western Arabic digits -> Persian digits.
_PERSIAN_DIGIT_MAP = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_persian_digits(value) -> str:
    """
    Convert any value containing Western digits (0-9) into Persian digits.
    """
    return str(value).translate(_PERSIAN_DIGIT_MAP)


def format_jalali_date(value, include_time=False) -> str:
    """
    Format a Gregorian datetime/date as a Persian date string.

    Args:
        value: The datetime/date to format.
        include_time: If True, includes time (HH:MM) in the output.

    Returns:
        Persian date string (e.g., "۲۰ مرداد ۱۴۰۵").
    """
    if not value:
        return ""

    # Convert to Jalali date
    if hasattr(value, "date"):
        jalali = jdatetime.date.fromgregorian(date=value.date())
    else:
        jalali = jdatetime.date.fromgregorian(date=value)

    day = to_persian_digits(jalali.day)
    month_name = PERSIAN_MONTH_NAMES[jalali.month - 1]
    year = to_persian_digits(jalali.year)

    result = f"{day} {month_name} {year}"

    # Add time if requested
    if include_time and hasattr(value, "time"):
        time_str = value.strftime("%H:%M")
        result += f"، ساعت {to_persian_digits(time_str)}"

    return result