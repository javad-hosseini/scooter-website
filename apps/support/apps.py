"""
Application configuration for the support app.
"""

from django.apps import AppConfig


class SupportConfig(AppConfig):
    """
    Configuration class for the support application.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.support"
    verbose_name = "پشتیبانی"