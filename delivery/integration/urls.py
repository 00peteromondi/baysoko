"""
URLs for e-commerce integration
"""
from django.urls import path
from . import views

app_name = 'integration'

urlpatterns = [
    # Webhook endpoints
    path('webhook/', views.platform_webhook, name='platform_webhook'),
    path('webhook/<int:platform_id>/', views.platform_webhook, name='platform_webhook_with_id'),
    path('webhook/baysoko/', views.baysoko_webhook, name='baysoko_webhook'),
    path('webhook/shopify/', views.shopify_webhook, name='shopify_webhook'),
    path('webhook/woocommerce/', views.woocommerce_webhook, name='woocommerce_webhook'),

    # Also register the shorter routes so callers that post to
    # /api/delivery/webhook/<platform>/ (without the extra 'webhook' segment)
    # continue to work for compatibility with tests and external integrations.
    path('baysoko/', views.baysoko_webhook, name='baysoko_webhook_short'),
    path('shopify/', views.shopify_webhook, name='shopify_webhook_short'),
    path('woocommerce/', views.woocommerce_webhook, name='woocommerce_webhook_short'),
    path('', views.platform_webhook, name='platform_webhook_root'),
    path('<int:platform_id>/', views.platform_webhook, name='platform_webhook_with_id_short'),
    
    # Test endpoints
    path('test/webhook/', views.WebhookTestView.as_view(), name='test_webhook'),
    
    # API endpoints for manual sync
    path('api/sync/', views.sync_platforms, name='sync_platforms'),
    path('api/sync/<int:platform_id>/', views.sync_platform, name='sync_platform'),
    path('api/orders/<int:order_id>/delivery/', views.get_order_delivery, name='order_delivery'),
]