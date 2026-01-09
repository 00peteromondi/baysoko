from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.urls import re_path
from listings import admin_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('listings.urls')),
    path('users/', include('users.urls')),
    path('chats/', include('chats.urls')),
    path('reviews/', include('reviews.urls')),
    path('blog/', include('blog.urls')),
    path('notifications/', include('notifications.urls')),
    path('storefront/', include('storefront.urls')),
    
    # Delivery System
    path('delivery/', include('delivery.urls')),
    
    # Social authentication
    path('accounts/', include('allauth.urls')),
    path('admin/webhook-config/', admin_views.configure_webhooks, name='admin_configure_webhooks'),
]

# Add webhook endpoints for delivery system
if settings.DELIVERY_SYSTEM_ENABLED:
    urlpatterns += [
        path('api/delivery/webhook/', include('delivery.integration.urls', namespace='delivery_webhook')),
        
    ]

# Custom error handlers
from django.conf.urls import handler500
handler500 = 'homabay_souq.views.custom_error_500'

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)