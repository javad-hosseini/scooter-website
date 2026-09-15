"""
Forms for the support application.

This module defines forms for creating tickets and sending messages.
Forms enforce validation on the server side and provide Persian labels.
"""

from django import forms

from .models import Ticket, TicketMessage
from .validators import validate_ticket_attachment, MAX_ATTACHMENTS_PER_MESSAGE


class MultipleFileInput(forms.ClearableFileInput):
    """Custom file input that allows multiple file selection."""

    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """
    Custom file field that accepts multiple files and validates each one.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        """
        Validate multiple uploaded files.

        Args:
            data: The uploaded files.
            initial: Initial data.

        Returns:
            list: List of validated file objects.

        Raises:
            ValidationError: If validation fails.
        """
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            if len(data) > MAX_ATTACHMENTS_PER_MESSAGE:
                raise forms.ValidationError(
                    f"حداکثر {MAX_ATTACHMENTS_PER_MESSAGE} فایل می‌توانید پیوست کنید."
                )
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]

        # Validate each file
        for file in result:
            if file:
                validate_ticket_attachment(file)

        return result


class TicketCreateForm(forms.Form):
    """
    Form for creating a new support ticket.
    """

    title = forms.CharField(
        max_length=200,
        label="عنوان تیکت",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "عنوان کوتاه و واضح بنویسید...",
        }),
        help_text="یک عنوان کوتاه و واضح برای مشکل خود بنویسید.",
    )

    subject = forms.ChoiceField(
        choices=Ticket.Subject.choices,
        label="موضوع",
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="موضوع اصلی تیکت را انتخاب کنید.",
    )

    message = forms.CharField(
        label="پیام",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 5,
            "placeholder": "مشکل خود را با جزئیات توضیح دهید...",
        }),
        help_text="مشکل خود را با جزئیات کامل توضیح دهید.",
    )

    attachments = MultipleFileField(
        label="پیوست‌ها",
        required=False,
        help_text="حداکثر ۳ فایل (JPG، PNG، WEBP یا PDF).",
    )


class TicketMessageForm(forms.Form):
    """
    Form for sending a message on an existing ticket.
    """

    message = forms.CharField(
        label="پیام",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 4,
            "placeholder": "پیام خود را بنویسید...",
        }),
        help_text="پیام خود را بنویسید.",
    )

    attachments = MultipleFileField(
        label="پیوست‌ها",
        required=False,
        help_text="حداکثر ۳ فایل (JPG، PNG، WEBP یا PDF).",
    )