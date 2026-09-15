"""
Admin configuration for the support application.

Provides a chat-like interface for support staff to view conversations,
reply to tickets, and manage ticket status. The admin interface is
optimized for non-technical support staff with clear Persian labels
and intuitive controls.
"""

from django import forms
from django.contrib import admin
from django.contrib import messages as django_messages
from django.shortcuts import redirect
from django.utils.html import format_html
from django.core.exceptions import ValidationError
import logging

from .models import Ticket, TicketMessage, TicketAttachment
from .services import send_support_message, close_ticket, reopen_ticket
from .validators import validate_ticket_attachment, MAX_ATTACHMENTS_PER_MESSAGE

logger = logging.getLogger(__name__)


class SupportReplyForm(forms.Form):
    """
    Form for support staff to reply to a ticket.

    Note: Multiple file uploads are handled manually in the view
    to avoid Django's FileInput widget limitations.
    """

    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'پاسخ خود را بنویسید...',
            'style': 'width: 100%; padding: 10px; border-radius: 8px; border: 1px solid #ccc; font-family: inherit;',
        }),
        label="پاسخ",
        help_text="پاسخ خود را برای کاربر بنویسید.",
    )


class TicketAttachmentInline(admin.TabularInline):
    """
    Inline display of attachments within a message.
    """

    model = TicketAttachment
    extra = 0
    readonly_fields = ["file", "original_name", "created_at", "file_link"]
    fields = ["file_link", "original_name", "created_at"]
    can_delete = False
    max_num = 0
    verbose_name = "پیوست"
    verbose_name_plural = "پیوست‌ها"

    def file_link(self, obj):
        """Display a download link for the file."""
        if obj.file:
            return format_html(
                '<a href="{}" target="_blank" style="color: #245C43;">دانلود فایل</a>',
                obj.file.url,
            )
        return "-"

    file_link.short_description = "فایل"

    def has_add_permission(self, request, obj=None):
        """Prevent adding attachments through inline."""
        return False


class TicketMessageInline(admin.TabularInline):
    """
    Chat-like inline display of messages within a ticket.
    """

    model = TicketMessage
    extra = 0
    readonly_fields = ["sender", "message", "created_at", "attachments_display"]
    fields = ["sender", "message", "attachments_display", "created_at"]
    can_delete = False
    max_num = 0
    verbose_name = "پیام"
    verbose_name_plural = "گفتگو"

    def attachments_display(self, obj):
        """Display attachments for this message."""
        attachments = obj.attachments.all()
        if not attachments:
            return "-"

        links = []
        for att in attachments:
            links.append(
                format_html(
                    '<a href="{}" target="_blank" style="color: #245C43; margin-left: 5px;">📎 {}</a>',
                    att.file.url,
                    att.original_name,
                )
            )
        return format_html(" ".join(str(link) for link in links))

    attachments_display.short_description = "پیوست‌ها"

    def has_add_permission(self, request, obj=None):
        """Prevent adding messages through inline."""
        return False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    """
    Admin interface for managing support tickets.

    Provides a chat-like view of the conversation and a reply form
    for support staff. Staff can also close and reopen tickets.
    """

    list_display = [
        "tracking_code_display",
        "title",
        "user",
        "subject",
        "status_display",
        "created_at",
        "updated_at",
        "message_count",
    ]

    list_filter = [
        "status",
        "subject",
        "created_at",
    ]

    search_fields = [
        "tracking_code",
        "title",
        "user__username",
        "user__email",
    ]

    ordering = ["-created_at"]

    readonly_fields = [
        "tracking_code",
        "user",
        "title",
        "subject",
        "created_at",
        "updated_at",
        "conversation_display",
    ]

    list_per_page = 25

    inlines = [TicketMessageInline]

    fieldsets = [
        (
            "اطلاعات تیکت",
            {
                "fields": (
                    "tracking_code",
                    "user",
                    "title",
                    "subject",
                    "status",
                ),
            },
        ),
        (
            "گفتگو",
            {
                "fields": ("conversation_display",),
                "classes": ("wide",),
            },
        ),
        (
            "زمان‌بندی",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    ]

    actions = [
        "close_tickets",
        "reopen_tickets",
    ]

    # Custom template for change form
    change_form_template = "admin/support/ticket_change_form.html"

    def has_add_permission(self, request):
        """Tickets are opened by customers, never created in the admin.

        tracking_code is generated by services.create_ticket() rather than in
        Ticket.save(), and it is read-only here, so an admin-created ticket
        would have no tracking code at all.
        """
        return False

    def get_urls(self):
        """Add custom URLs for reply and status actions."""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:object_id>/reply/',
                self.admin_site.admin_view(self.reply_view),
                name='support-ticket-reply',
            ),
            path(
                '<int:object_id>/close/',
                self.admin_site.admin_view(self.close_view),
                name='support-ticket-close',
            ),
            path(
                '<int:object_id>/reopen/',
                self.admin_site.admin_view(self.reopen_view),
                name='support-ticket-reopen',
            ),
        ]
        return custom_urls + urls

    def reply_view(self, request, object_id):
        """
        Handle support staff reply to a ticket.

        Args:
            request: The HTTP request.
            object_id: The ticket ID.

        Returns:
            HttpResponse: Redirect back to the ticket change page.
        """
        ticket = self.get_object(request, object_id)

        if request.method == 'POST':
            form = SupportReplyForm(request.POST)

            if form.is_valid():
                try:
                    # Handle multiple files manually
                    attachments = request.FILES.getlist('attachments')

                    # Limit to 3 attachments
                    if len(attachments) > MAX_ATTACHMENTS_PER_MESSAGE:
                        django_messages.error(
                            request,
                            f"حداکثر {MAX_ATTACHMENTS_PER_MESSAGE} فایل می‌توانید پیوست کنید.",
                        )
                        return redirect('admin:support_ticket_change', object_id=object_id)

                    # Staff uploads go through the same extension/MIME/size/content
                    # checks as customer uploads — the customer form validates in
                    # MultipleFileField, and this path must not be the weaker one.
                    for uploaded in attachments:
                        validate_ticket_attachment(uploaded)

                    send_support_message(
                        ticket=ticket,
                        user=request.user,
                        message_text=form.cleaned_data['message'],
                        attachments=attachments if attachments else None,
                    )

                    django_messages.success(request, "پاسخ شما با موفقیت ارسال شد.")
                    return redirect(
                        'admin:support_ticket_change',
                        object_id=object_id,
                    )
                except ValidationError as exc:
                    django_messages.error(request, exc.messages[0] if exc.messages else "درخواست نامعتبر است.")
                except Exception:
                    logger.exception("Unexpected error while sending support admin reply")
                    django_messages.error(request, "خطایی در ارسال پاسخ رخ داد. لطفاً دوباره تلاش کنید.")
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        django_messages.error(request, f"{field}: {error}")

        return redirect('admin:support_ticket_change', object_id=object_id)

    def close_view(self, request, object_id):
        """
        Handle closing a ticket.

        Args:
            request: The HTTP request.
            object_id: The ticket ID.

        Returns:
            HttpResponse: Redirect back to the ticket change page.
        """
        ticket = self.get_object(request, object_id)

        if request.method == 'POST':
            close_ticket(ticket)
            django_messages.success(request, "تیکت با موفقیت بسته شد.")

        return redirect('admin:support_ticket_change', object_id=object_id)

    def reopen_view(self, request, object_id):
        """
        Handle reopening a ticket.

        Args:
            request: The HTTP request.
            object_id: The ticket ID.

        Returns:
            HttpResponse: Redirect back to the ticket change page.
        """
        ticket = self.get_object(request, object_id)

        if request.method == 'POST':
            reopen_ticket(ticket)
            django_messages.success(request, "تیکت با موفقیت باز شد.")

        return redirect('admin:support_ticket_change', object_id=object_id)

    def conversation_display(self, obj):
        """Display the full conversation in a safely escaped chat-like format."""
        messages_list = (
            obj.messages.select_related("sender")
            .prefetch_related("attachments")
            .order_by("created_at")
        )

        html = [
            '<div style="max-height: 500px; overflow-y: auto; padding: 10px; '
            'background: #f9f9f9; border-radius: 8px;">'
        ]

        for msg in messages_list:
            is_customer = msg.sender == obj.user
            sender_name = msg.sender.get_full_name() or msg.sender.username
            message_style = (
                "background: #E8F5E9; border-radius: 12px; padding: 10px 15px; "
                "border-top-right-radius: 4px;"
                if is_customer
                else "background: #245C43; color: white; border-radius: 12px; "
                "padding: 10px 15px; border-top-left-radius: 4px;"
            )
            side = "flex-start" if is_customer else "flex-end"
            sender_label = "کاربر:" if is_customer else "پشتیبانی:"
            extra_message_style = "" if is_customer else "color: white;"

            html.append(
                format_html(
                    '<div style="display: flex; justify-content: {}; margin-bottom: 15px;">'
                    '<div style="max-width: 70%;">'
                    '<div style="{}">'
                    '<div style="font-size: 0.8em; opacity: 0.8; margin-bottom: 5px;">'
                    '<strong>{}</strong> {}</div>'
                    '<div style="line-height: 1.6; white-space: pre-wrap; {}">{}</div>'
                    '</div>'
                    '<div style="font-size: 0.75em; color: #999; margin-top: 5px; '
                    'padding-right: 5px;">{}</div>'
                    '</div></div>',
                    side,
                    message_style,
                    sender_label,
                    sender_name,
                    extra_message_style,
                    msg.message,
                    msg.created_at.strftime("%Y/%m/%d %H:%M"),
                )
            )

            attachments = msg.attachments.all()
            if attachments:
                html.append(
                    '<div style="margin: 5px 0 15px 0; padding-right: 20px;">'
                )
                for att in attachments:
                    html.append(
                        format_html(
                            '<a href="{}" target="_blank" rel="noopener noreferrer" '
                            'style="display: inline-block; margin-left: 10px; padding: 5px 10px; '
                            'background: #fff; border: 1px solid #ddd; border-radius: 6px; '
                            'color: #245C43; text-decoration: none; font-size: 0.85em;">'
                            '📎 {}</a>',
                            att.file.url,
                            att.original_name,
                        )
                    )
                html.append("</div>")

        html.append("</div>")
        return format_html("".join(html))

    conversation_display.short_description = "گفتگو"

    def tracking_code_display(self, obj):
        """Display tracking code prominently."""
        return format_html(
            '<span style="font-weight: bold; font-size: 1.1em;">{}</span>',
            obj.tracking_code,
        )

    tracking_code_display.short_description = "کد پیگیری"
    tracking_code_display.admin_order_field = "tracking_code"

    def status_display(self, obj):
        """Display status with color coding."""
        status_colors = {
            Ticket.Status.WAITING_FOR_SUPPORT: "#E87932",
            Ticket.Status.WAITING_FOR_USER: "#245C43",
            Ticket.Status.CLOSED: "#6E756F",
        }

        color = status_colors.get(obj.status, "#6E756F")

        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 4px 10px; border-radius: 12px; '
            'font-size: 0.85em;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_display.short_description = "وضعیت"
    status_display.admin_order_field = "status"

    def message_count(self, obj):
        """Display the number of messages in the ticket."""
        count = obj.messages.count()
        return format_html(
            '<span style="font-size: 0.9em;">{} پیام</span>',
            count,
        )

    message_count.short_description = "تعداد پیام‌ها"

    def save_model(self, request, obj, form, change):
        """Handle status changes when saving from admin."""
        if change:
            old_obj = Ticket.objects.get(pk=obj.pk)
            if old_obj.status != obj.status:
                if obj.status == Ticket.Status.CLOSED and old_obj.status != Ticket.Status.CLOSED:
                    close_ticket(obj)
                elif old_obj.status == Ticket.Status.CLOSED and obj.status != Ticket.Status.CLOSED:
                    reopen_ticket(obj)
                else:
                    super().save_model(request, obj, form, change)
                return
        super().save_model(request, obj, form, change)

    @admin.action(description="بستن تیکت‌های انتخاب شده")
    def close_tickets(self, request, queryset):
        """Close selected tickets."""
        count = 0
        for ticket in queryset:
            if not ticket.is_closed:
                close_ticket(ticket)
                count += 1
        self.message_user(request, f"{count} تیکت بسته شد.")

    @admin.action(description="باز کردن تیکت‌های انتخاب شده")
    def reopen_tickets(self, request, queryset):
        """Reopen selected closed tickets."""
        count = 0
        for ticket in queryset:
            if ticket.is_closed:
                reopen_ticket(ticket)
                count += 1
        self.message_user(request, f"{count} تیکت باز شد.")


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    """Admin interface for managing ticket messages."""

    list_display = [
        "ticket_tracking_code",
        "sender",
        "short_preview_display",
        "created_at",
        "attachment_count",
    ]

    list_filter = ["created_at"]

    search_fields = [
        "ticket__tracking_code",
        "sender__username",
        "message",
    ]

    ordering = ["-created_at"]

    readonly_fields = [
        "ticket",
        "sender",
        "message",
        "created_at",
        "updated_at",
    ]

    list_per_page = 50

    inlines = [TicketAttachmentInline]

    def ticket_tracking_code(self, obj):
        """Display the ticket tracking code."""
        return obj.ticket.tracking_code

    ticket_tracking_code.short_description = "کد پیگیری"
    ticket_tracking_code.admin_order_field = "ticket__tracking_code"

    def short_preview_display(self, obj):
        """Display a short preview of the message."""
        return obj.short_preview

    short_preview_display.short_description = "پیش‌نمایش پیام"

    def attachment_count(self, obj):
        """Display the number of attachments."""
        count = obj.attachments.count()
        if count > 0:
            return format_html(
                '<span style="color: #245C43;">{} فایل</span>',
                count,
            )
        return "-"

    attachment_count.short_description = "پیوست‌ها"


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    """Admin interface for managing ticket attachments."""

    list_display = [
        "original_name",
        "ticket_tracking_code",
        "file_link",
        "created_at",
    ]

    search_fields = [
        "original_name",
        "message__ticket__tracking_code",
    ]

    ordering = ["-created_at"]

    readonly_fields = [
        "message",
        "file",
        "original_name",
        "created_at",
    ]

    list_per_page = 50

    def ticket_tracking_code(self, obj):
        """Display the ticket tracking code."""
        return obj.message.ticket.tracking_code

    ticket_tracking_code.short_description = "کد پیگیری"

    def file_link(self, obj):
        """Display a link to the uploaded file."""
        if obj.file:
            return format_html(
                '<a href="{}" target="_blank">دانلود</a>',
                obj.file.url,
            )
        return "-"

    file_link.short_description = "فایل"
