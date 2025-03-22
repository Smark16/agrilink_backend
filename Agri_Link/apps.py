# Agri_Link/apps.py
from django.apps import AppConfig

class AgriLinkConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Agri_Link'

    def ready(self):
        # Import the signal handler here to ensure it's connected
        from . import signals  # noqa
