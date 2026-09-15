"""
Business logic services for the support application.

This module centralizes the core business logic for ticket management:
- Tracking code generation
- Ticket creation
- Message sending with business rule enforcement
- Ticket closing and reopening

Centralizing this logic prevents duplication and ensures consistent
business rule enforcement across views, forms, and admin actions.
"""

import random
import logging
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError

from .models import Ticket, TicketMessage, TicketAttachment

logger = logging.getLogger(__name__)


def generate_tracking_code():
    """
    Generate a unique 6-digit tracking code for a support ticket.

    The code is generated randomly to prevent sequential guessing.
    The database uniqueness constraint is the final authority; callers retry on collisions.

    Returns:
        str: A unique 6-digit numeric tracking code.

    Raises:
        RuntimeError: If a unique code cannot be generated after 100 attempts.
    """
    for _ in range(100):  # Limit attempts to prevent infinite loop
        code = str(random.randint(100000, 999999))
        if not Ticket.objects.filter(tracking_code=code).exists():
            return code

    raise RuntimeError("Unable to generate unique tracking code after 100 attempts.")


@transaction.atomic
def create_ticket(user, title, subject, message_text, attachments=None):
    """
    Create a new support ticket with the initial message.

    This function is atomic to ensure the ticket and initial message
    are created together or not at all.

    Args:
        user: The user creating the ticket.
        title: Ticket title.
        subject: Ticket subject (must be from Ticket.Subject choices).
        message_text: Initial message text.
        attachments: Optional list of file objects to attach.

    Returns:
        Ticket: The created ticket instance.

    Raises:
        ValidationError: If validation fails.
        RuntimeError: If tracking code generation fails.
    """
    # The uniqueness constraint is the final authority. The retry loop
    # handles the rare case where another request wins the same code race.
    for _ in range(100):
        tracking_code = generate_tracking_code()
        try:
            with transaction.atomic():
                ticket = Ticket.objects.create(
                    user=user,
                    tracking_code=tracking_code,
                    title=title,
                    subject=subject,
                    status=Ticket.Status.WAITING_FOR_SUPPORT,
                )
        except IntegrityError:
            continue
        break
    else:
        raise RuntimeError("Unable to create a unique support tracking code.")


    # Create initial message
    message = TicketMessage.objects.create(
        ticket=ticket,
        sender=user,
        message=message_text,
    )

    # Create attachments if provided
    if attachments:
        for file in attachments:
            TicketAttachment.objects.create(
                message=message,
                file=file,
                original_name=file.name,
            )

    return ticket


@transaction.atomic
def send_customer_message(ticket, user, message_text, attachments=None):
    """
    Send a message from a customer on a ticket.

    Enforces the business rule that customers can only send messages
    when the ticket status is WAITING_FOR_USER.

    Args:
        ticket: The ticket to send the message on.
        user: The customer sending the message.
        message_text: The message text.
        attachments: Optional list of file objects.

    Returns:
        TicketMessage: The created message.

    Raises:
        ValidationError: If the user is not the ticket owner or
            if the ticket status doesn't allow customer messages.
    """
    # Verify ownership
    if ticket.user != user:
        raise ValidationError("شما دسترسی به این تیکت ندارید.")

    # Check business rule
    if not ticket.can_customer_send_message:
        raise ValidationError(
            "شما نمی‌توانید در حال حاضر پیام ارسال کنید. "
            "منتظر پاسخ پشتیبانی باشید."
        )

    # Create message
    message = TicketMessage.objects.create(
        ticket=ticket,
        sender=user,
        message=message_text,
    )

    # Create attachments
    if attachments:
        for file in attachments:
            TicketAttachment.objects.create(
                message=message,
                file=file,
                original_name=file.name,
            )

    # Update ticket status
    ticket.status = Ticket.Status.WAITING_FOR_SUPPORT
    ticket.save(update_fields=["status", "updated_at"])

    return message


@transaction.atomic
def send_support_message(ticket, user, message_text, attachments=None):
    """
    Send a message from support staff on a ticket.

    Support staff can reply when the ticket is waiting for support.

    Args:
        ticket: The ticket to send the message on.
        user: The support staff member sending the message.
        message_text: The message text.
        attachments: Optional list of file objects.

    Returns:
        TicketMessage: The created message.

    Raises:
        ValidationError: If the ticket is closed or if the status
            doesn't allow support messages.
    """
    # Authorization is part of the service boundary, not only the admin UI.
    if not getattr(user, "is_staff", False):
        raise ValidationError("شما مجاز به ارسال پیام پشتیبانی نیستید.")

    # Check if ticket is closed
    if ticket.is_closed:
        raise ValidationError("این تیکت بسته شده است و امکان ارسال پیام ندارد.")

    # Check business rule
    if not ticket.can_support_send_message:
        raise ValidationError(
            "این تیکت در انتظار پاسخ کاربر است."
        )

    # Create message
    message = TicketMessage.objects.create(
        ticket=ticket,
        sender=user,
        message=message_text,
    )

    # Create attachments
    if attachments:
        for file in attachments:
            TicketAttachment.objects.create(
                message=message,
                file=file,
                original_name=file.name,
            )

    # Update ticket status
    ticket.status = Ticket.Status.WAITING_FOR_USER
    ticket.save(update_fields=["status", "updated_at"])

    return message


@transaction.atomic
def close_ticket(ticket):
    """
    Close a support ticket.

    Args:
        ticket: The ticket to close.

    Returns:
        Ticket: The updated ticket.
    """
    if not ticket.is_closed:
        ticket.status = Ticket.Status.CLOSED
        ticket.save(update_fields=["status", "updated_at"])
    return ticket


@transaction.atomic
def reopen_ticket(ticket):
    """
    Reopen a closed support ticket.

    When reopened, the ticket status is set to WAITING_FOR_USER
    to allow the customer to respond.

    Args:
        ticket: The ticket to reopen.

    Returns:
        Ticket: The updated ticket.
    """
    if ticket.is_closed:
        ticket.status = Ticket.Status.WAITING_FOR_USER
        ticket.save(update_fields=["status", "updated_at"])
    return ticket