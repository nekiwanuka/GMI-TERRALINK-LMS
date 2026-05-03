"""
WSGI config for GMI Terralink Logistics Management System.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gmi_terralink.settings")

application = get_wsgi_application()
