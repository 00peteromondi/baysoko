from django.urls import path
from . import views

urlpatterns = [
    # Main views
    path('', views.inbox, name='inbox'),
    path('conversation/<int:pk>/', views.conversation_detail, name='conversation-detail'),
    path('start/<int:listing_id>/<int:recipient_id>/', views.start_conversation, name='start-conversation'),
    
    # Essential API endpoints
    path('api/unread-messages-count/', views.unread_messages_count, name='unread-messages-count'),
    path('api/send-message/', views.send_message_api, name='send-message-api'),
    path('api/mark-read/<int:conversation_id>/', views.mark_messages_read, name='mark-messages-read'),
    path('api/get-new-messages/<int:conversation_id>/', views.get_new_messages, name='get-new-messages'),
    path('api/conversations-list/', views.conversations_list, name='conversations-list'),
    path('api/get-message-status/<int:conversation_id>/', views.get_message_status, name='get-message-status'),
    path('api/search-users/', views.search_users, name='search-users'),
    path('api/my-listings/', views.my_listings, name='my-listings'),
    path('api/get-online-users/', views.api_get_online_users, name='api-get-online-users'),  # Changed name
    path('api/update-online-status/', views.update_online_status, name='update-online-status'),
    path('api/conversation-status/<int:conversation_id>/', views.get_conversation_status, name='conversation-status'),
    path('api/group-conversations/', views.group_conversations, name='group-conversations'),
    
    # Typing indicators
    path('api/send-typing/<int:conversation_id>/', views.send_typing_indicator, name='send-typing'),
    path('api/check-typing/<int:conversation_id>/', views.check_typing, name='check-typing'),
    
    # Call endpoints (WebRTC)
    path('api/send-call-offer/', views.send_call_offer, name='send-call-offer'),
    path('api/get-call-answer/<str:call_id>/', views.get_call_answer, name='get-call-answer'),
    path('api/send-ice-candidate/', views.send_ice_candidate, name='send-ice-candidate'),
    path('api/end-call/', views.end_call, name='end-call'),
    
    # Other optional endpoints
    path('api/delete-message/<int:message_id>/', views.delete_message, name='delete-message'),
    path('api/delete-conversation/<int:conversation_id>/', views.delete_conversation, name='delete-conversation'),
    path('api/mute-conversation/<int:conversation_id>/', views.mute_conversation, name='mute-conversation'),
]