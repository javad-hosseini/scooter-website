"""
URL patterns for the support application.

Defines the customer-facing URLs for the support system.
"""

from django.urls import path, register_converter
from django.urls.converters import StringConverter

from . import views


class TrackingCodeConverter(StringConverter):
    """
    URL converter for 6-digit tracking codes.
    """

    regex = r"\d{6}"


# Register the converter
register_converter(TrackingCodeConverter, "tracking_code")

app_name = "support"

urlpatterns = [
    path("", views.TicketListView.as_view(), name="ticket_list"),
    path("new/", views.TicketCreateView.as_view(), name="ticket_create"),
    path(
        "tickets/<tracking_code:tracking_code>/",
        views.TicketDetailView.as_view(),
        name="ticket_detail",
    ),
]