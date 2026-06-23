from django.urls import path, include
from . import views

app_name = 'delivery_api'

urlpatterns = [
    path('deliveries/', views.DeliveryViewSet.as_view({'get': 'list'}), name='delivery-list'),
    path('deliveries/<int:pk>/', views.DeliveryViewSet.as_view({'get': 'retrieve'}), name='delivery-detail'),
    path('deliveries/<int:pk>/update-status/', views.DeliveryViewSet.as_view({'post': 'update_status'}), name='update-status'),
    
    path('drivers/', views.DriverViewSet.as_view({'get': 'list'}), name='driver-list'),
    path('drivers/<int:pk>/', views.DriverViewSet.as_view({'get': 'retrieve'}), name='driver-detail'),
    path('drivers/<int:pk>/update-location/', views.DriverViewSet.as_view({'post': 'update_location'}), name='update-location'),
    
    path('services/', views.ServiceViewSet.as_view({'get': 'list'}), name='service-list'),
    
    path('calculate-fee/', views.calculate_delivery_fee_api, name='calculate-fee'),
    path('track/<str:tracking_number>/', views.track_delivery_api, name='track-delivery'),
    
    
    # Analytics endpoints
    path('analytics/', views.delivery_analytics_api, name='analytics'),
    path('analytics/status-distribution/', views.status_distribution_api, name='status-distribution'),
    path('analytics/weekly-activity/', views.weekly_activity_api, name='weekly-activity'),
    path('analytics/driver-performance/', views.driver_performance_api, name='driver-performance'),
    path('analytics/zone-performance/', views.zone_performance_api, name='zone-performance'),
    # Webhook receiver for external delivery systems
    path('webhook/', views.webhook_receiver, name='webhook'),
]