"""ASGI config (optional, for future async support)."""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ebs_project.settings')

application = get_asgi_application()