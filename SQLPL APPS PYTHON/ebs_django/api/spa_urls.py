"""SPA URL — serves index.html for all non-API routes."""
from django.urls import re_path
from django.views.generic import TemplateView

urlpatterns = [
    # Serve SPA for all non-API/admin/static paths
    re_path(r"^(?!api/|admin/|static/|media/).*$",
            TemplateView.as_view(template_name="index.html")),
]