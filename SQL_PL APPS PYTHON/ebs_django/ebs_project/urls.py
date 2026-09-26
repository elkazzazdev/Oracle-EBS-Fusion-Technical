"""
URL configuration for EBS R12 Explorer.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Customize Django Admin branding
admin.site.site_header = "EBS R12 Explorer — Admin"
admin.site.site_title = "EBS R12 Explorer"
admin.site.index_title = "Administration Panel"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('', include('api.spa_urls')),  # SPA served at root
]

# Serve media/static in dev
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)