"""
URL configuration for inventory_api project.
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),

    # API endpoints
    path('api/auth/', include('apps.accounts.urls')),
    path('api/', include('apps.business.urls')),
    path('api/', include('apps.products.urls')),
    path('api/', include('apps.inventory.urls')),
    path('api/', include('apps.reports.urls')),

    # API documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
