"""
ASGI config for GMI Terralink Logistics Management System.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gmi_terralink.settings")

application = get_asgi_application()
