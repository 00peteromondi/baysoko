from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views
from .api import urls as api_urls

app_name = 'delivery'

urlpatterns = [
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('dashboard/stats/', views.dashboard_stats, name='dashboard_stats'),
    
    # Delivery Management
    path('dashboard/recent-deliveries/', views.recent_deliveries, name='recent_deliveries'),
    path('dashboard/chart-data/', views.chart_data, name='chart_data'),
    path('deliveries/', views.DeliveryListView.as_view(), name='delivery_list'),
    path('deliveries/create/', views.CreateDeliveryView.as_view(), name='create_delivery'),
    path('deliveries/<int:pk>/', views.DeliveryDetailView.as_view(), name='delivery_detail'),
    path('deliveries/<int:pk>/update-status/', views.UpdateDeliveryStatusView.as_view(), name='update_status'),
    path('deliveries/<int:pk>/submit-proof/', views.submit_proof, name='submit_proof'),
    path('deliveries/bulk-update/', views.bulk_update_status, name='bulk_update_status'),
    
    # Driver Management
    path('driver/dashboard/', views.DriverDashboardView.as_view(), name='driver_dashboard'),
    path('driver/assignments/', views.driver_assignments, name='driver_assignments'),
    path('driver/updates/', views.driver_updates, name='driver_updates'),
    path('driver/update-location/', views.update_driver_location, name='update_driver_location'),
    path('driver/update-status/', views.update_driver_status, name='update_driver_status'),
    path('driver/active-deliveries/', views.driver_active_deliveries, name='driver_active_deliveries'),
    
    # Quick Stats & Notifications
    path('quick-stats/', views.quick_stats, name='quick_stats'),
    path('notification-count/', views.notification_count, name='notification_count'),
    
    # Tracking
    path('track/<str:tracking_number>/', views.track_delivery, name='track_delivery'),
    path('confirm-delivery/', views.confirm_delivery, name='confirm_delivery'),
    
    # Reports & Analytics
    path('reports/', views.delivery_reports, name='reports'),
    path('analytics/', views.delivery_analytics, name='analytics'),

    path('api/orders/', views.get_user_orders, name='get_user_orders'),
    path('api/order/<int:order_id>/details/', views.get_order_details, name='order_details'),
    path('api/calculate-fee/', views.calculate_delivery_fee_api, name='calculate_fee_api'),
    path('orders/<int:order_id>/manage/', views.CreateDeliveryView.as_view(), name='manage_order'),
    
    # API
    path('api/', include(api_urls)),
    
    # Authentication
    path('login/', auth_views.LoginView.as_view(
        template_name='delivery/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(
        next_page='delivery:login'
    ), name='logout'),
]