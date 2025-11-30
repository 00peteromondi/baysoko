from django.urls import path
from . import views, mpesa_webhook

app_name = 'storefront'

urlpatterns = [
    path('', views.store_list, name='store_list'),
    path('store/<slug:slug>/', views.store_detail, name='store_detail'),
    path('store/<slug:store_slug>/product/<slug:slug>/', views.product_detail, name='product_detail'),
    # seller dashboard
    path('dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('dashboard/store/create/', views.store_create, name='store_create'),
    path('dashboard/store/<slug:slug>/edit/', views.store_edit, name='store_edit'),
    
    path('dashboard/store/<slug:slug>/upgrade/', views.store_upgrade, name='upgrade'),
    # Legacy/alternate name kept for backwards compatibility with tests and callers
    path('dashboard/store/<slug:slug>/upgrade/', views.store_upgrade, name='store_upgrade'),
    path('dashboard/store/<slug:store_slug>/product/create/', views.product_create, name='product_create'),
    path('dashboard/product/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('dashboard/product/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('dashboard/image/<int:pk>/delete/', views.image_delete, name='image_delete'),
    
    # Store image management
    path('dashboard/store/<slug:slug>/logo/delete/', views.delete_logo, name='delete_logo'),
    path('dashboard/store/<slug:slug>/cover/delete/', views.delete_cover, name='delete_cover'),
    
    # Subscription management
    path('dashboard/store/<slug:slug>/subscription/', views.subscription_manage, name='subscription_manage'),
    path('dashboard/store/<slug:slug>/subscription/retry/', views.retry_payment, name='retry_payment'),
    path('dashboard/store/<slug:slug>/subscription/cancel/', views.cancel_subscription, name='cancel_subscription'),
    
    # Analytics
    path('dashboard/analytics/', views.seller_analytics, name='seller_analytics'),
    path('dashboard/store/<slug:slug>/analytics/', views.store_analytics, name='store_analytics'),
    
    # Payment monitoring
    path('dashboard/monitor/payments/', views.payment_monitor, name='payment_monitor'),
    
    # M-Pesa webhook
    path('mpesa/callback/', mpesa_webhook.mpesa_callback, name='mpesa_callback'),
]
