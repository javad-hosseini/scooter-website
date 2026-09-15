"""
Tests for the support application.

Tests cover:
- Ticket creation and tracking code generation
- Authorization and ownership
- Message flow and business rules
- Closed ticket behavior
- Attachment validation

python manage.py test apps.support

"""

import itertools

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, RequestFactory
from django.urls import reverse
from PIL import Image
from io import BytesIO

from .forms import TicketCreateForm, TicketMessageForm
from .models import Ticket, TicketMessage, TicketAttachment
from .services import (
    generate_tracking_code,
    create_ticket,
    send_customer_message,
    send_support_message,
    close_ticket,
    reopen_ticket,
)
from .validators import validate_ticket_attachment, MAX_ATTACHMENTS_PER_MESSAGE


User = get_user_model()

# Unique-per-call suffix for the generated email/mobile below.
_user_counter = itertools.count(1)


def make_user(username, password="testpass123", **extra):
    """Create a test user for this project's user model.

    CustomUser declares `email` unique and `mobile` unique, so the plain
    `create_user(username=..., password=...)` these tests were written against
    gives every user an empty email and the second one fails on the unique
    constraint. A unique email and mobile are derived per call unless the test
    supplies its own.
    """
    n = next(_user_counter)
    extra.setdefault("email", f"support-test-{n}@example.com")
    extra.setdefault("mobile", f"0915{n:07d}")
    extra.setdefault("fullname", username)
    return User.objects.create_user(username=username, password=password, **extra)


class TicketModelTests(TestCase):
    """
    Test the Ticket model and tracking code generation.
    """

    def setUp(self):
        self.user = make_user(
            username="testuser",
            password="testpass123",
        )
        self.staff_user = make_user(
            username="staffuser",
            password="testpass123",
            is_staff=True,
        )

    def test_tracking_code_generation(self):
        """Test that tracking code is 6 digits."""
        code = generate_tracking_code()
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_tracking_code_uniqueness(self):
        """Test that generated codes are unique."""
        codes = set()
        for _ in range(10):
            code = generate_tracking_code()
            self.assertNotIn(code, codes)
            codes.add(code)

    def test_ticket_creation(self):
        """Test creating a ticket with initial message."""
        ticket = create_ticket(
            user=self.user,
            title="Test Ticket",
            subject=Ticket.Subject.ORDER,
            message_text="This is a test message.",
        )

        self.assertEqual(ticket.user, self.user)
        self.assertEqual(ticket.status, Ticket.Status.WAITING_FOR_SUPPORT)
        self.assertTrue(ticket.tracking_code.isdigit())
        self.assertEqual(len(ticket.tracking_code), 6)
        self.assertEqual(ticket.messages.count(), 1)

    def test_ticket_str_method(self):
        """Test string representation."""
        ticket = create_ticket(
            user=self.user,
            title="Test Ticket",
            subject=Ticket.Subject.ORDER,
            message_text="Test message",
        )
        self.assertIn(ticket.tracking_code, str(ticket))
        self.assertIn(ticket.title, str(ticket))


class TicketAuthorizationTests(TestCase):
    """
    Test ticket ownership and authorization.
    """

    def setUp(self):
        self.user = make_user(
            username="testuser",
            password="testpass123",
        )
        self.other_user = make_user(
            username="otheruser",
            password="testpass123",
        )

        self.ticket = create_ticket(
            user=self.user,
            title="Test Ticket",
            subject=Ticket.Subject.ORDER,
            message_text="Test message",
        )

    def test_ticket_ownership_verification(self):
        """Test that services verify ticket ownership."""
        # Customer sending message on own ticket should work
        # First, support needs to reply to change status
        support_user = make_user(
            username="support",
            password="testpass123",
            is_staff=True,
        )
        send_support_message(
            ticket=self.ticket,
            user=support_user,
            message_text="Support reply",
        )

        # Now customer can send
        message = send_customer_message(
            ticket=self.ticket,
            user=self.user,
            message_text="Customer reply",
        )
        self.assertIsNotNone(message)

    def test_non_owner_cannot_send_message(self):
        """Test that non-owner cannot send message on someone else's ticket."""
        support_user = make_user(
            username="support",
            password="testpass123",
            is_staff=True,
        )
        send_support_message(
            ticket=self.ticket,
            user=support_user,
            message_text="Support reply",
        )

        # Other user tries to send message
        with self.assertRaises(ValidationError):
            send_customer_message(
                ticket=self.ticket,
                user=self.other_user,
                message_text="Trying to hijack ticket",
            )


class TicketMessageFlowTests(TestCase):
    """
    Test the message flow and business rules.
    """

    def setUp(self):
        self.customer = make_user(
            username="customer",
            password="testpass123",
        )
        self.support_staff = make_user(
            username="support",
            password="testpass123",
            is_staff=True,
        )

        self.ticket = create_ticket(
            user=self.customer,
            title="Test Flow",
            subject=Ticket.Subject.PRODUCT,
            message_text="Initial message",
        )

    def test_initial_status(self):
        """Test initial ticket status."""
        self.assertEqual(self.ticket.status, Ticket.Status.WAITING_FOR_SUPPORT)

    def test_customer_cannot_send_twice(self):
        """Test that customer cannot send consecutive messages."""
        with self.assertRaises(ValidationError):
            send_customer_message(
                ticket=self.ticket,
                user=self.customer,
                message_text="Second message",
            )

    def test_non_staff_cannot_send_support_message(self):
        non_staff = make_user(
            username="notstaff",
            password="testpass123",
        )
        with self.assertRaises(ValidationError):
            send_support_message(
                ticket=self.ticket,
                user=non_staff,
                message_text="Unauthorized support reply",
            )

    def test_support_can_reply(self):
        """Test that support can reply to waiting ticket."""
        message = send_support_message(
            ticket=self.ticket,
            user=self.support_staff,
            message_text="Support reply",
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.WAITING_FOR_USER)

    def test_full_conversation_flow(self):
        """Test complete conversation flow."""
        # Support replies
        send_support_message(
            ticket=self.ticket,
            user=self.support_staff,
            message_text="How can I help?",
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.WAITING_FOR_USER)

        # Customer replies
        send_customer_message(
            ticket=self.ticket,
            user=self.customer,
            message_text="I have a problem.",
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.WAITING_FOR_SUPPORT)

        # Support replies again
        send_support_message(
            ticket=self.ticket,
            user=self.support_staff,
            message_text="Let me help you.",
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.WAITING_FOR_USER)


class TicketClosedTests(TestCase):
    """
    Test closed ticket behavior.
    """

    def setUp(self):
        self.customer = make_user(
            username="customer",
            password="testpass123",
        )
        self.support_staff = make_user(
            username="support",
            password="testpass123",
            is_staff=True,
        )

        self.ticket = create_ticket(
            user=self.customer,
            title="Test Closed",
            subject=Ticket.Subject.ACCOUNT,
            message_text="Initial message",
        )

    def test_close_ticket(self):
        """Test closing a ticket."""
        close_ticket(self.ticket)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.CLOSED)

    def test_customer_cannot_message_closed_ticket(self):
        """Test that customer cannot message a closed ticket."""
        close_ticket(self.ticket)
        with self.assertRaises(ValidationError):
            send_customer_message(
                ticket=self.ticket,
                user=self.customer,
                message_text="Hello?",
            )

    def test_reopen_ticket(self):
        """Test reopening a closed ticket."""
        close_ticket(self.ticket)
        reopen_ticket(self.ticket)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.WAITING_FOR_USER)

    def test_support_cannot_message_closed_ticket(self):
        """Test that support cannot message a closed ticket."""
        close_ticket(self.ticket)
        with self.assertRaises(ValidationError):
            send_support_message(
                ticket=self.ticket,
                user=self.support_staff,
                message_text="Hello?",
            )


class TicketAttachmentTests(TestCase):
    """
    Test attachment validation and security.
    """

    def create_test_image(self):
        """Create a test image file."""
        img = Image.new("RGB", (100, 100), color="red")
        img_io = BytesIO()
        img.save(img_io, format="JPEG")
        img_io.seek(0)
        return SimpleUploadedFile(
            "test.jpg",
            img_io.read(),
            content_type="image/jpeg",
        )

    def create_test_pdf(self):
        """Create a test PDF file."""
        content = b"%PDF-1.4 test content"
        return SimpleUploadedFile(
            "test.pdf",
            content,
            content_type="application/pdf",
        )

    def test_valid_jpg_attachment(self):
        """Test that valid JPG passes validation."""
        file = self.create_test_image()
        try:
            category = validate_ticket_attachment(file)
            self.assertEqual(category, "image")
        except ValidationError:
            self.fail("Valid JPG should pass validation")

    def test_valid_pdf_attachment(self):
        """Test that valid PDF passes validation."""
        file = self.create_test_pdf()
        try:
            category = validate_ticket_attachment(file)
            self.assertEqual(category, "document")
        except ValidationError:
            self.fail("Valid PDF should pass validation")

    def test_invalid_extension(self):
        """Test that invalid extension is rejected."""
        file = SimpleUploadedFile(
            "test.exe",
            b"malicious content",
            content_type="application/octet-stream",
        )
        with self.assertRaises(ValidationError):
            validate_ticket_attachment(file)

    def test_invalid_mime_type(self):
        """Test that mismatched MIME type is rejected."""
        file = SimpleUploadedFile(
            "test.jpg",
            b"not really an image",
            content_type="application/x-php",
        )
        with self.assertRaises(ValidationError):
            validate_ticket_attachment(file)

    def test_oversized_image(self):
        """Test that oversized image is rejected."""
        # Create a large file (> 5MB)
        content = b"0" * (5 * 1024 * 1024 + 1)
        file = SimpleUploadedFile(
            "large.jpg",
            content,
            content_type="image/jpeg",
        )
        with self.assertRaises(ValidationError):
            validate_ticket_attachment(file)


class TicketFormTests(TestCase):
    """Form-level validation for TicketCreateForm/TicketMessageForm."""

    def test_ticket_create_form_valid_data(self):
        form = TicketCreateForm(data={
            "title": "مشکل در سفارش",
            "subject": Ticket.Subject.ORDER,
            "message": "سفارش من هنوز نرسیده است.",
        })
        self.assertTrue(form.is_valid())

    def test_ticket_create_form_requires_title(self):
        form = TicketCreateForm(data={
            "subject": Ticket.Subject.ORDER,
            "message": "پیام",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)

    def test_ticket_create_form_rejects_invalid_subject(self):
        form = TicketCreateForm(data={
            "title": "عنوان",
            "subject": "NOT_A_REAL_SUBJECT",
            "message": "پیام",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("subject", form.errors)

    def test_attachments_are_optional(self):
        form = TicketMessageForm(data={"message": "پیام بدون پیوست"})
        self.assertTrue(form.is_valid())

    def test_too_many_attachments_rejected(self):
        def _image():
            img = Image.new("RGB", (10, 10), color="blue")
            buf = BytesIO()
            img.save(buf, format="JPEG")
            buf.seek(0)
            return SimpleUploadedFile("a.jpg", buf.read(), content_type="image/jpeg")

        files = [_image() for _ in range(MAX_ATTACHMENTS_PER_MESSAGE + 1)]
        form = TicketMessageForm(
            data={"message": "پیام با پیوست زیاد"},
            files={"attachments": files},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("attachments", form.errors)


class TicketListViewTests(TestCase):
    """HTTP-level tests for the customer ticket history page."""

    def setUp(self):
        self.user = make_user(username="owner", password="x")
        self.other_user = make_user(username="stranger", password="x")
        self.own_ticket = create_ticket(
            user=self.user, title="تیکت من", subject=Ticket.Subject.ORDER,
            message_text="پیام من",
        )
        self.other_ticket = create_ticket(
            user=self.other_user, title="تیکت دیگری", subject=Ticket.Subject.ORDER,
            message_text="پیام دیگری",
        )

    def test_requires_login(self):
        response = self.client.get(reverse("support:ticket_list"))
        self.assertEqual(response.status_code, 302)

    def test_only_shows_own_tickets(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("support:ticket_list"))
        self.assertEqual(response.status_code, 200)
        tickets = list(response.context["tickets"])
        self.assertIn(self.own_ticket, tickets)
        self.assertNotIn(self.other_ticket, tickets)


class TicketCreateViewTests(TestCase):
    """HTTP-level tests for creating a new ticket."""

    def setUp(self):
        self.user = make_user(username="creator", password="x")

    def test_requires_login(self):
        response = self.client.get(reverse("support:ticket_create"))
        self.assertEqual(response.status_code, 302)

    def test_get_renders_form(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("support:ticket_create"))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context["form"], TicketCreateForm)

    def test_valid_post_creates_ticket_and_redirects(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("support:ticket_create"), {
            "title": "تیکت جدید",
            "subject": Ticket.Subject.PRODUCT,
            "message": "توضیح مشکل",
        })
        ticket = Ticket.objects.get(user=self.user)
        self.assertRedirects(
            response,
            reverse("support:ticket_detail", args=[ticket.tracking_code]),
        )
        self.assertEqual(ticket.title, "تیکت جدید")
        self.assertEqual(ticket.messages.count(), 1)

    def test_invalid_post_rerenders_with_errors(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("support:ticket_create"), {
            "title": "",
            "subject": Ticket.Subject.PRODUCT,
            "message": "توضیح مشکل",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())
        self.assertEqual(Ticket.objects.count(), 0)


class TicketDetailViewTests(TestCase):
    """HTTP-level tests for viewing/replying to a ticket - ownership is critical here."""

    def setUp(self):
        self.owner = make_user(username="ticket-owner", password="x")
        self.stranger = make_user(username="not-owner", password="x")
        self.support_staff = make_user(
            username="support-agent", password="x", is_staff=True,
        )
        self.ticket = create_ticket(
            user=self.owner, title="تیکت محرمانه", subject=Ticket.Subject.ACCOUNT,
            message_text="پیام اولیه",
        )

    def test_requires_login(self):
        response = self.client.get(
            reverse("support:ticket_detail", args=[self.ticket.tracking_code])
        )
        self.assertEqual(response.status_code, 302)

    def test_owner_can_view(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("support:ticket_detail", args=[self.ticket.tracking_code])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "تیکت محرمانه")

    def test_non_owner_gets_404_not_someone_elses_ticket(self):
        """Security: a logged-in user must never see another user's ticket."""
        self.client.force_login(self.stranger)
        response = self.client.get(
            reverse("support:ticket_detail", args=[self.ticket.tracking_code])
        )
        self.assertEqual(response.status_code, 404)

    def test_nonexistent_tracking_code_404s(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("support:ticket_detail", args=["000000"])
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_can_reply_after_support_message(self):
        send_support_message(ticket=self.ticket, user=self.support_staff, message_text="پاسخ پشتیبانی")
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("support:ticket_detail", args=[self.ticket.tracking_code]),
            {"message": "پاسخ من به پشتیبانی"},
        )
        self.assertRedirects(
            response,
            reverse("support:ticket_detail", args=[self.ticket.tracking_code]),
        )
        self.assertEqual(self.ticket.messages.count(), 3)

    def test_reply_out_of_turn_shows_form_error_not_crash(self):
        """Customer replying twice in a row is a business-rule violation,
        not a server error - the view must catch it and re-render."""
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("support:ticket_detail", args=[self.ticket.tracking_code]),
            {"message": "پیام دوم بدون پاسخ پشتیبانی"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ticket.messages.count(), 1)  # nothing new was added

    def test_stranger_cannot_post_message_to_others_ticket(self):
        self.client.force_login(self.stranger)
        response = self.client.post(
            reverse("support:ticket_detail", args=[self.ticket.tracking_code]),
            {"message": "تلاش برای دخالت"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.ticket.messages.count(), 1)