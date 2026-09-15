"""
Support application models.

This module defines the core models for the customer support system:
- Ticket: Represents a customer support conversation.
- TicketMessage: Individual messages within a ticket.
- TicketAttachment: Files attached to messages.

Important business rules:
- Customers cannot send consecutive messages without a support reply.
- Closed tickets cannot receive new customer messages.
- Each ticket has a unique 6-digit tracking code.
"""

from django.conf import settings
from django.core.validators import MinLengthValidator, MaxLengthValidator
from django.db import models
from django.utils import timezone


class Ticket(models.Model):
    """
    Represents a single customer support conversation.

    A Ticket contains messages between a customer and support staff.
    The status field controls who can send messages at any given time.
    """

    class Subject(models.TextChoices):
        """Controlled subject choices for support tickets."""

        ORDER = "ORDER", "ثبت سفارش"
        PAYMENT = "PAYMENT", "پرداخت"
        SHIPPING = "SHIPPING", "ارسال و تحویل"
        PRODUCT = "PRODUCT", "مشکل محصول"
        RETURN = "RETURN", "مرجوعی"
        ACCOUNT = "ACCOUNT", "حساب کاربری"
        WEBSITE = "WEBSITE", "مشکل سایت"
        OTHER = "OTHER", "سایر"

    class Status(models.TextChoices):
        """
        Ticket conversation states.

        WAITING_FOR_SUPPORT: Customer sent a message, waiting for support.
        WAITING_FOR_USER: Support replied, waiting for customer.
        CLOSED: Conversation ended, no more messages allowed.
        """

        WAITING_FOR_SUPPORT = "WAITING_FOR_SUPPORT", "در انتظار پشتیبانی"
        WAITING_FOR_USER = "WAITING_FOR_USER", "در انتظار کاربر"
        CLOSED = "CLOSED", "بسته شده"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_tickets",
        verbose_name="کاربر",
        help_text="کاربری که این تیکت را ایجاد کرده است.",
    )

    tracking_code = models.CharField(
        max_length=6,
        unique=True,
        validators=[
            MinLengthValidator(6),
            MaxLengthValidator(6),
        ],
        verbose_name="کد پیگیری",
        help_text="کد پیگیری ۶ رقمی منحصر به فرد برای این تیکت.",
    )

    title = models.CharField(
        max_length=200,
        verbose_name="عنوان تیکت",
        help_text="عنوان کوتاه و واضح برای تیکت پشتیبانی.",
    )

    subject = models.CharField(
        max_length=20,
        choices=Subject.choices,
        verbose_name="موضوع",
        help_text="موضوع اصلی تیکت پشتیبانی را انتخاب کنید.",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING_FOR_SUPPORT,
        verbose_name="وضعیت",
        help_text="وضعیت فعلی تیکت و نوبت ارسال پیام.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد",
        help_text="تاریخ و زمان ایجاد تیکت.",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="تاریخ بروزرسانی",
        help_text="تاریخ و زمان آخرین تغییر در تیکت.",
    )

    class Meta:
        verbose_name = "تیکت پشتیبانی"
        verbose_name_plural = "تیکت‌های پشتیبانی"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tracking_code"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.tracking_code} - {self.title}"

    @property
    def is_closed(self):
        """Check if the ticket is closed."""
        return self.status == self.Status.CLOSED

    @property
    def can_customer_send_message(self):
        """Check if customer can send a message based on current status."""
        return self.status == self.Status.WAITING_FOR_USER

    @property
    def can_support_send_message(self):
        """Check if support staff can send a message based on current status."""
        return self.status == self.Status.WAITING_FOR_SUPPORT


class TicketMessage(models.Model):
    """
    Represents an individual message within a ticket conversation.

    Each message has an explicit sender and belongs to exactly one ticket.
    """

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="تیکت",
        help_text="تیکتی که این پیام به آن تعلق دارد.",
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_messages",
        verbose_name="ارسال‌کننده",
        help_text="کاربری که این پیام را ارسال کرده است.",
    )

    message = models.TextField(
        verbose_name="پیام",
        help_text="متن پیام.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ارسال",
        help_text="تاریخ و زمان ارسال پیام.",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="تاریخ بروزرسانی",
        help_text="تاریخ و زمان آخرین ویرایش پیام.",
    )

    class Meta:
        verbose_name = "پیام تیکت"
        verbose_name_plural = "پیام‌های تیکت"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["ticket", "created_at"]),
            models.Index(fields=["sender"]),
        ]

    def __str__(self):
        return f"پیام {self.pk} - تیکت {self.ticket.tracking_code}"

    @property
    def short_preview(self):
        """Return a short preview of the message for admin display."""
        return self.message[:100] + "..." if len(self.message) > 100 else self.message


class TicketAttachment(models.Model):
    """
    Represents a file attached to a ticket message.

    Security considerations:
    - Files are validated for type, size, and content.
    - Uploaded files are stored in a non-executable media directory.
    """

    message = models.ForeignKey(
        TicketMessage,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="پیام",
        help_text="پیامی که این فایل به آن پیوست شده است.",
    )

    file = models.FileField(
        upload_to="support/attachments/%Y/%m/",
        verbose_name="فایل",
        help_text="فایل پیوست شده به پیام.",
    )

    original_name = models.CharField(
        max_length=255,
        verbose_name="نام اصلی فایل",
        help_text="نام اصلی فایل قبل از آپلود.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ آپلود",
        help_text="تاریخ و زمان آپلود فایل.",
    )

    class Meta:
        verbose_name = "پیوست تیکت"
        verbose_name_plural = "پیوست‌های تیکت"
        ordering = ["created_at"]

    def __str__(self):
        return self.original_name