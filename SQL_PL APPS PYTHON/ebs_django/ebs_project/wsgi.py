"""
WSGI config for EBS R12 Explorer.
Production server: waitress
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ebs_project.settings')

application = get_wsgi_application()