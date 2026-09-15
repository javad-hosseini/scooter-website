"""
File validation utilities for the support application.

This module provides secure file validation for ticket attachments.
It enforces file type, size, and content validation to prevent
malicious file uploads.

Security considerations:
- Validates both file extension and MIME type.
- Uses PIL for image validation.
- Prevents executable and script file uploads.
"""

import os
from io import BytesIO

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible
from PIL import Image


# Allowed file extensions and their corresponding MIME types
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf"}

ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

ALLOWED_DOCUMENT_MIME_TYPES = {
    "application/pdf",
}

# File size limits (in bytes)
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10 MB

# Maximum number of attachments per message
MAX_ATTACHMENTS_PER_MESSAGE = 3


def get_file_extension(filename):
    """
    Extract the file extension from a filename.

    Args:
        filename: The name of the file.

    Returns:
        str: Lowercase file extension including the dot (e.g., '.jpg').
    """
    return os.path.splitext(filename)[1].lower()


def validate_file_size(file, max_size):
    """
    Validate that a file does not exceed the maximum allowed size.

    Args:
        file: The uploaded file object.
        max_size: Maximum allowed file size in bytes.

    Raises:
        ValidationError: If the file exceeds the maximum size.
    """
    if file.size > max_size:
        raise ValidationError(
            f"حجم فایل نباید بیشتر از {max_size // (1024 * 1024)} مگابایت باشد."
        )


def validate_image_content(file):
    """
    Validate that the uploaded file is a valid image.

    Uses PIL to verify the actual image content, not just the extension.

    Args:
        file: The uploaded file object.

    Raises:
        ValidationError: If the file is not a valid image.
    """
    try:
        img = Image.open(file)
        img.verify()
        # Reset file pointer after verify
        file.seek(0)
    except Exception:
        raise ValidationError("فایل تصویری معتبر نیست.")


def validate_ticket_attachment(file):
    """
    Validate a ticket attachment file for security and type.

    This function validates:
    - File extension is allowed.
    - MIME type matches the extension category.
    - File size is within limits.
    - Image files are valid images.

    Args:
        file: The uploaded file object.

    Returns:
        str: The category of the file ('image' or 'document').

    Raises:
        ValidationError: If the file fails any validation checks.
    """
    extension = get_file_extension(file.name)

    # Check if extension is allowed
    if extension in ALLOWED_IMAGE_EXTENSIONS:
        category = "image"
        max_size = MAX_IMAGE_SIZE
        allowed_mime_types = ALLOWED_IMAGE_MIME_TYPES
    elif extension in ALLOWED_DOCUMENT_EXTENSIONS:
        category = "document"
        max_size = MAX_DOCUMENT_SIZE
        allowed_mime_types = ALLOWED_DOCUMENT_MIME_TYPES
    else:
        raise ValidationError(
            f"فرمت فایل '{extension}' مجاز نیست. "
            "فقط فرمت‌های JPG، JPEG، PNG، WEBP و PDF مجاز هستند."
        )

    # Validate MIME type
    content_type = getattr(file, "content_type", None)
    if content_type and content_type not in allowed_mime_types:
        raise ValidationError(
            f"نوع فایل '{content_type}' با پسوند '{extension}' مطابقت ندارد."
        )

    # Validate file size
    validate_file_size(file, max_size)

    # Additional validation for images
    if category == "image":
        validate_image_content(file)

    return category