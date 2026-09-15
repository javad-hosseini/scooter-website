"""
Views for the support application.

This module implements the customer-facing views for the support system:
- Ticket list (history)
- Create new ticket
- Ticket detail with conversation

All views enforce authentication and ticket ownership.
"""

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic import ListView
from django.contrib import messages

from .forms import TicketCreateForm, TicketMessageForm
from .models import Ticket
from .services import create_ticket, send_customer_message

logger = logging.getLogger(__name__)


class TicketListView(LoginRequiredMixin, ListView):
    """
    Display the authenticated user's support tickets.
    """

    model = Ticket
    template_name = "support/ticket_list.html"
    context_object_name = "tickets"
    paginate_by = 20

    def get_queryset(self):
        """
        Return tickets belonging to the current user.

        Returns:
            QuerySet: Tickets owned by the current user, newest first.
        """
        return (
            Ticket.objects.filter(user=self.request.user)
            .select_related("user")
            .prefetch_related("messages")
            .order_by("-created_at")
        )


class TicketCreateView(LoginRequiredMixin, View):
    """
    Create a new support ticket.
    """

    template_name = "support/ticket_create.html"

    def get(self, request):
        """
        Display the ticket creation form.

        Args:
            request: The HTTP request.

        Returns:
            HttpResponse: Rendered form.
        """
        form = TicketCreateForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        """
        Process ticket creation form submission.

        Args:
            request: The HTTP request.

        Returns:
            HttpResponse: Redirect to ticket detail on success, or form with errors.
        """
        form = TicketCreateForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                # Extract attachments
                attachments = form.cleaned_data.get("attachments", [])

                # Create ticket
                ticket = create_ticket(
                    user=request.user,
                    title=form.cleaned_data["title"],
                    subject=form.cleaned_data["subject"],
                    message_text=form.cleaned_data["message"],
                    attachments=attachments,
                )

                messages.success(request, "تیکت شما با موفقیت ثبت شد.")
                return redirect(
                    "support:ticket_detail",
                    tracking_code=ticket.tracking_code,
                )

            except ValidationError as exc:
                form.add_error(None, exc)
            except Exception:
                logger.exception("Unexpected error while creating support ticket")
                messages.error(request, "خطایی در ثبت تیکت رخ داد. لطفاً دوباره تلاش کنید.")

        return render(request, self.template_name, {"form": form})


class TicketDetailView(LoginRequiredMixin, View):
    """
    Display ticket details and conversation, and handle message sending.
    """

    template_name = "support/ticket_detail.html"

    def get_ticket(self, request, tracking_code):
        """
        Get ticket ensuring the current user is the owner.

        Args:
            request: The HTTP request.
            tracking_code: The ticket tracking code.

        Returns:
            Ticket: The ticket if user is owner.

        Raises:
            Http404: If ticket doesn't exist or user is not owner.
        """
        return get_object_or_404(
            Ticket,
            tracking_code=tracking_code,
            user=request.user,
        )

    def get(self, request, tracking_code):
        """
        Display ticket details and messages.

        Args:
            request: The HTTP request.
            tracking_code: The ticket tracking code.

        Returns:
            HttpResponse: Rendered ticket detail page.
        """
        ticket = self.get_ticket(request, tracking_code)
        messages_list = (
            ticket.messages.select_related("sender")
            .prefetch_related("attachments")
            .order_by("created_at")
        )

        form = TicketMessageForm()

        context = {
            "ticket": ticket,
            "messages_list": messages_list,
            "form": form,
        }

        return render(request, self.template_name, context)

    def post(self, request, tracking_code):
        """
        Handle customer message submission.

        Enforces business rules server-side.

        Args:
            request: The HTTP request.
            tracking_code: The ticket tracking code.

        Returns:
            HttpResponse: Redirect to ticket detail on success, or form with errors.
        """
        ticket = self.get_ticket(request, tracking_code)
        form = TicketMessageForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                attachments = form.cleaned_data.get("attachments", [])

                send_customer_message(
                    ticket=ticket,
                    user=request.user,
                    message_text=form.cleaned_data["message"],
                    attachments=attachments,
                )

                messages.success(request, "پیام شما با موفقیت ارسال شد.")
                return redirect(
                    "support:ticket_detail",
                    tracking_code=ticket.tracking_code,
                )

            except ValidationError as exc:
                form.add_error(None, exc)
            except Exception:
                logger.exception("Unexpected error while sending customer support message")
                messages.error(request, "خطایی در ارسال پیام رخ داد. لطفاً دوباره تلاش کنید.")

        # If form is invalid, re-render the page with errors
        messages_list = (
            ticket.messages.select_related("sender")
            .prefetch_related("attachments")
            .order_by("created_at")
        )

        context = {
            "ticket": ticket,
            "messages_list": messages_list,
            "form": form,
        }

        return render(request, self.template_name, context)