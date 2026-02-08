# storefront/urls.py (updated)
from django.urls import path
from . import views, mpesa_webhook
from .urls_inventory import inventory_patterns
from .urls_bulk import bulk_patterns, bundle_patterns
from . import views_subscription

app_name = 'storefront'

urlpatterns = [
    path('', views.store_list, name='store_list'),
    path('store/<slug:slug>/', views.store_detail, name='store_detail'),
    path('store/<slug:store_slug>/product/<slug:slug>/', views.product_detail, name='product_detail'),
    
    # seller dashboard
    path('dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('dashboard/store/create/', views.store_create, name='store_create'),
    path('dashboard/store/<slug:slug>/edit/', views.store_edit, name='store_edit'),
    
    # Legacy/alternate name kept for backwards compatibility
    path('dashboard/store/<slug:slug>/upgrade/', views_subscription.subscription_manage, name='store_upgrade'),
    
    # Product management
    path('dashboard/store/<slug:store_slug>/product/create/', views.product_create, name='product_create'),
    path('dashboard/product/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('dashboard/product/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('dashboard/image/<int:pk>/delete/', views.image_delete, name='image_delete'),
    
    # Store image management
    path('dashboard/store/<slug:slug>/logo/delete/', views.delete_logo, name='delete_logo'),
    path('dashboard/store/<slug:slug>/cover/delete/', views.delete_cover, name='delete_cover'),    
    
    # Store Reviews
    path('store/<slug:slug>/review/', views.store_review_create, name='store_review_create'),
    path('store/<slug:slug>/reviews/', views.store_reviews, name='store_reviews'),
    path('store/<slug:slug>/review/<int:review_id>/update/', views.store_review_update, name='store_review_update'),
    path('store/<slug:slug>/review/<int:review_id>/delete/', views.store_review_delete, name='store_review_delete'),
    path('store/<slug:slug>/review/<int:review_id>/helpful/', views.mark_review_helpful, name='mark_review_helpful'),
    path('store/<slug:slug>/analytics/views/', views.store_views_analytics, name='store_views_analytics'),
   # Enhanced Subscription Management
    path('dashboard/store/<slug:slug>/subscription/plans/', views_subscription.subscription_plan_select, name='subscription_plan_select'),
    path('dashboard/store/<slug:slug>/subscription/payment-options/', views_subscription.subscription_payment_options, name='subscription_payment_options'),
    path('dashboard/store/<slug:slug>/subscription/manage/', views_subscription.subscription_manage, name='subscription_manage'),
    path('dashboard/store/<slug:slug>/subscription/change-plan/', views_subscription.subscription_change_plan, name='subscription_change_plan'),
    path('dashboard/store/<slug:slug>/subscription/renew/', views_subscription.subscription_renew, name='subscription_renew'),
    path('dashboard/store/<slug:slug>/subscription/cancel/', views_subscription.subscription_cancel, name='cancel_subscription'),
    
    path('dashboard/store/<slug:slug>/subscription/invoice/<int:payment_id>/', views_subscription.subscription_invoice, name='subscription_invoice'),
    path('dashboard/store/<slug:slug>/subscription/settings/', views_subscription.subscription_settings, name='subscription_settings'),
    path('dashboard/store/<slug:slug>/subscription/retry/', views_subscription.retry_payment, name='retry_payment'),
    # Movement APIs
    path('store/<slug:slug>/inventory/movements/<int:movement_id>/undo/', views.undo_movement, name='undo_movement'),
    path('store/<slug:slug>/inventory/movements/<int:movement_id>/',  views.get_movement_details, name='movement_details'),
    
    # Admin subscription views
    path('admin/subscriptions/', views.admin_subscription_list, name='admin_subscription_list'),
    path('admin/subscriptions/<int:subscription_id>/', views.admin_subscription_detail, name='admin_subscription_detail'),
     
    # Analytics
    path('dashboard/analytics/', views.seller_analytics, name='seller_analytics'),
    path('dashboard/store/<slug:slug>/analytics/', views.store_analytics, name='store_analytics'),
    path('api/analytics/seller/summary/', views.seller_analytics_summary, name='seller_analytics_summary'),
    path('api/analytics/store/<slug:slug>/summary/', views.store_analytics_summary, name='store_analytics_summary'),
    path('api/analytics/revenue-trend/', views.revenue_trend_data, name='revenue_trend_data'),
    path('api/analytics/customer-insights/', views.customer_insights, name='customer_insights'),
    path('api/analytics/store/<slug:slug>/product-performance/', views.product_performance, name='product_performance'),
    
    # Payment monitoring
    path('dashboard/monitor/payments/', views.payment_monitor, name='payment_monitor'),
    path('dashboard/monitor/store/<slug:slug>/withdraw/', views.request_withdrawal, name='request_withdrawal'),
    path('dashboard/verify-payout/<slug:slug>/', views.start_payout_verification, name='start_payout_verification'),
    path('mpesa/payout-verification-callback/', views.payout_verification_callback, name='payout_verification_callback'),
    
    # M-Pesa webhook
    path('mpesa/callback/', mpesa_webhook.mpesa_callback, name='mpesa_callback'),
    # Legacy callback path used in some envs/settings (keep for compatibility)
    path('mpesa-callback/', mpesa_webhook.mpesa_callback, name='mpesa_callback_legacy'),
]

urlpatterns += inventory_patterns + bulk_patterns + bundle_patterns