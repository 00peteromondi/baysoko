from django.urls import path
from . import views

urlpatterns = [
    path('', views.notification_list, name='notification-list'),
    path('preferences/', views.notification_preferences, name='notification-preferences'),
    path('mark-read/<int:notification_id>/', views.mark_notification_read, name='mark-notification-read'),
    path('mark-all-read/', views.mark_all_read, name='mark-all-read'),
    path('delete/<int:notification_id>/', views.delete_notification, name='delete-notification'),
    path('clear-all/', views.clear_all_notifications, name='clear-all-notifications'),
    path('api/unread-count/', views.get_unread_count, name='unread-notification-count'),
]