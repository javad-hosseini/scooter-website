"""
Image Factory using Pillow (PIL) to generate mock placeholder images
with solid colors, contrasting backgrounds, and crisp English typography.
"""

import io
import random
import textwrap
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont

# Curated palette of modern solid background and text colors
THEME_PALETTES = [
    # (background_hex, primary_text_hex, secondary_text_hex, accent_hex)
    ('#0f172a', '#f8fafc', '#94a3b8', '#38bdf8'),  # Slate Navy & Cyan
    ('#18181b', '#ffffff', '#a1a1aa', '#ef4444'),  # Carbon Dark & Crimson
    ('#022c22', '#ecfdf5', '#6ee7b7', '#10b981'),  # Deep Emerald & Mint
    ('#1e1b4b', '#eef2ff', '#a5b4fc', '#6366f1'),  # Midnight Indigo & Violet
    ('#311042', '#fdf4ff', '#f0abfc', '#d946ef'),  # Deep Plum & Magenta
    ('#292524', '#fafaf9', '#d6d3d1', '#f97316'),  # Warm Stone & Sunset Orange
    ('#0c4a6e', '#f0f9ff', '#7dd3fc', '#0284c7'),  # Ocean Deep & Electric Blue
    ('#172554', '#eff6ff', '#93c5fd', '#3b82f6'),  # Royal Blue & Sky
    ('#1c1917', '#fafaf9', '#a8a29e', '#eab308'),  # Dark Obsidian & Gold
    ('#3f3f46', '#ffffff', '#e4e4e7', '#00f0ff'),  # Cyber Zinc & Neon Cyan
]


def _get_font(size: int):
    """Load a scalable font with fallback."""
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        # For older Pillow versions without size parameter
        return ImageFont.load_default()


def generate_solid_image(
    width: int,
    height: int,
    title: str,
    subtitle: str = '',
    category_badge: str = '',
    bg_color: str | None = None,
    primary_text_color: str | None = None,
    secondary_text_color: str | None = None,
    accent_color: str | None = None,
    file_format: str = 'WEBP',
) -> ContentFile:
    """
    Generate a solid-colored image with English text and return a Django ContentFile.
    """
    palette = random.choice(THEME_PALETTES)
    bg = bg_color or palette[0]
    txt_primary = primary_text_color or palette[1]
    txt_secondary = secondary_text_color or palette[2]
    accent = accent_color or palette[3]

    # Create solid base image
    img = Image.new('RGB', (width, height), color=bg)
    draw = ImageDraw.Draw(img)

    # Decorative subtle accent border
    border_thickness = max(2, min(width, height) // 150)
    draw.rectangle(
        [(border_thickness, border_thickness), (width - border_thickness, height - border_thickness)],
        outline=accent,
        width=border_thickness,
    )

    # Determine font sizes based on image dimensions
    base_unit = min(width, height)
    title_size = max(16, int(base_unit * 0.065))
    subtitle_size = max(12, int(base_unit * 0.038))
    badge_size = max(11, int(base_unit * 0.032))

    title_font = _get_font(title_size)
    subtitle_font = _get_font(subtitle_size)
    badge_font = _get_font(badge_size)

    # Prepare text wrapping
    wrap_width = max(18, int(width / (title_size * 0.65)))
    wrapped_lines = textwrap.wrap(title.upper(), width=wrap_width)
    if len(wrapped_lines) > 3:
        wrapped_lines = wrapped_lines[:3]
        wrapped_lines[-1] += '...'

    # Calculate layout positions
    line_spacing = int(title_size * 1.3)
    total_title_height = len(wrapped_lines) * line_spacing

    # Top Badge (e.g. "ELECTRIC SCOOTER" or "NeX Go OFFICIAL")
    if category_badge:
        badge_text = f" {category_badge.upper()} "
        badge_y = int(height * 0.20)
        draw.text(
            (width // 2, badge_y),
            badge_text,
            fill=accent,
            anchor='mm',
            font=badge_font,
        )

    # Centered Title
    start_y = (height - total_title_height) // 2
    if category_badge:
        start_y += int(height * 0.05)

    for i, line in enumerate(wrapped_lines):
        y = start_y + (i * line_spacing)
        draw.text(
            (width // 2, y),
            line,
            fill=txt_primary,
            anchor='mm',
            font=title_font,
        )

    # Subtitle / Specs at bottom (e.g. "1200x630 | 500W DUAL MOTOR")
    if subtitle:
        sub_y = min(height - int(height * 0.15), start_y + total_title_height + int(height * 0.08))
        draw.text(
            (width // 2, sub_y),
            subtitle.upper(),
            fill=txt_secondary,
            anchor='mm',
            font=subtitle_font,
        )

    # Save to in-memory bytes
    buffer = io.BytesIO()
    save_format = file_format.upper()
    if save_format == 'WEBP':
        img.save(buffer, format='WEBP', quality=85, method=4)
    else:
        img.save(buffer, format='JPEG', quality=85)

    buffer.seek(0)
    return ContentFile(buffer.getvalue())


def create_category_image(title: str, subtitle: str = 'SCOOTER CATEGORY') -> ContentFile:
    """800x600 WebP banner for a category."""
    return generate_solid_image(
        width=800,
        height=600,
        title=title,
        subtitle=subtitle,
        category_badge='CATEGORY OVERVIEW',
    )


def create_product_cover_image(product_name: str, brand: str = 'NeX Go') -> ContentFile:
    """1000x1000 WebP primary cover image for product."""
    return generate_solid_image(
        width=1000,
        height=1000,
        title=product_name,
        subtitle=f'{brand} PERFORMANCE SCOOTER',
        category_badge=f'{brand} OFFICIAL',
    )


def create_product_grid_image(product_name: str, brand: str = 'NeX Go') -> ContentFile:
    """600x600 WebP grid card image for product listing."""
    return generate_solid_image(
        width=600,
        height=600,
        title=product_name,
        subtitle=brand,
        category_badge='SERIES 2026',
    )


def create_product_gallery_image(product_name: str, color_name: str, color_hex: str) -> ContentFile:
    """800x800 WebP gallery image with color accent matching the variant."""
    return generate_solid_image(
        width=800,
        height=800,
        title=f'{product_name}',
        subtitle=f'COLOR VARIANT: {color_name.upper()}',
        category_badge='PRODUCT GALLERY',
        accent_color=color_hex if color_hex and color_hex.startswith('#') else None,
    )


def create_article_cover_image(title: str, category_tag: str = 'SCOOTER GUIDE') -> ContentFile:
    """1200x630 WebP cover image (1.91:1 ratio) for blog article."""
    return generate_solid_image(
        width=1200,
        height=630,
        title=title,
        subtitle='NEX GO EDITORIAL & INSIGHTS',
        category_badge=category_tag,
    )
