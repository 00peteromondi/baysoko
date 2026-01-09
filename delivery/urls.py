from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views
from .api import urls as api_urls  # This should now work

app_name = 'delivery'

urlpatterns = [
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # Delivery Management
    path('deliveries/', views.DeliveryListView.as_view(), name='delivery_list'),
    path('deliveries/create/', views.CreateDeliveryView.as_view(), name='create_delivery'),
    path('deliveries/<int:pk>/', views.DeliveryDetailView.as_view(), name='delivery_detail'),
    path('deliveries/<int:pk>/update-status/', views.UpdateDeliveryStatusView.as_view(), name='update_status'),
    path('deliveries/<int:pk>/submit-proof/', views.submit_proof, name='submit_proof'),
    path('deliveries/bulk-update/', views.bulk_update_status, name='bulk_update_status'),
    
    # Driver Management
    path('driver/dashboard/', views.DriverDashboardView.as_view(), name='driver_dashboard'),
    path('driver/update-location/', views.update_driver_location, name='update_driver_location'),
    
    # Tracking
    path('track/<str:tracking_number>/', views.track_delivery, name='track_delivery'),
    
    # Reports & Analytics
    path('reports/', views.delivery_reports, name='reports'),
    path('analytics/', views.delivery_analytics, name='analytics'),
    
    # API
    path('api/', include(api_urls)),  # This includes all API endpoints
    
    # Authentication
    path('login/', auth_views.LoginView.as_view(
        template_name='delivery/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(
        next_page='delivery:login'
    ), name='logout'),
]