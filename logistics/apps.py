"""
Django app configuration for logistics
"""

from django.apps import AppConfig


class LogisticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "logistics"
    verbose_name = "GMI TERRALINK Logistics Portal Management System"

    def ready(self):
        from . import signals  # noqa: F401
