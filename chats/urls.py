from django.urls import path
from . import views

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('conversation/<int:pk>/', views.conversation_detail, name='conversation-detail'),
    path('start/<int:listing_id>/<int:recipient_id>/', views.start_conversation, name='start-conversation'),
    path('api/unread-messages-count/', views.unread_messages_count, name='unread-messages-count'),
    path('api/send-message/', views.send_message_api, name='send-message-api'),
    path('api/mark-read/<int:conversation_id>/', views.mark_messages_read, name='mark-messages-read'),
]