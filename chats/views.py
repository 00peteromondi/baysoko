# views.py - UPDATED WITH PROPER ONLINE STATUS
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count, Subquery, OuterRef, Max
from django.utils import timezone
from datetime import timedelta
import json
import logging
from .models import Conversation, Message, UserOnlineStatus
from .forms import MessageForm

logger = logging.getLogger(__name__)

# HELPER FUNCTIONS
def update_user_online_status(user):
    """Update user's online status"""
    status, created = UserOnlineStatus.objects.get_or_create(user=user)
    status.last_active = timezone.now()
    
    # User is considered online if active in last 3 minutes
    if (timezone.now() - status.last_active).seconds < 180:
        status.is_online = True
        status.last_seen = timezone.now()
    else:
        status.is_online = False
        
    status.save(update_fields=['is_online', 'last_active', 'last_seen'])
    return status

def get_online_user_ids():
    """Get list of online user IDs"""
    try:
        three_minutes_ago = timezone.now() - timedelta(minutes=3)
        online_statuses = UserOnlineStatus.objects.filter(
            last_active__gte=three_minutes_ago,
            is_online=True
        )
        return set(status.user_id for status in online_statuses)
    except Exception as e:
        logger.error(f"Error getting online users: {e}")
        return set()

def format_last_seen(last_seen):
    """Format last seen time"""
    if not last_seen:
        return "Never"
    
    now = timezone.now()
    diff = now - last_seen
    
    if diff.days > 365:
        return f"{diff.days // 365} year{'s' if diff.days // 365 > 1 else ''} ago"
    elif diff.days > 30:
        return f"{diff.days // 30} month{'s' if diff.days // 30 > 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"

def format_timestamp(timestamp):
    """Format timestamp for display"""
    today = timezone.now().date()
    message_date = timestamp.date()
    
    if message_date == today:
        return timestamp.strftime("%I:%M %p")
    elif message_date == today - timedelta(days=1):
        return "Yesterday"
    else:
        return message_date.strftime("%b %d")

# VIEWS
@login_required
def inbox(request):
    """Inbox view with modern messaging interface"""
    # Update current user's online status
    update_user_online_status(request.user)
    
    # Check if we should open a specific conversation
    open_conversation_id = request.GET.get('open')
    
    # Get all conversations for the user
    conversations = Conversation.objects.filter(
        participants=request.user,
        is_archived=False
    ).annotate(
        unread_count=Count(
            'messages',
            filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user)
        ),
        last_message_time=Max('messages__timestamp'),
        last_message_id=Subquery(
            Message.objects.filter(
                conversation=OuterRef('pk')
            ).order_by('-timestamp').values('id')[:1]
        )
    ).prefetch_related('participants').order_by('-last_message_time')
    
    # Get online user IDs
    online_user_ids = get_online_user_ids()
    
    # Format conversation data for template
    conversations_data = []
    open_conversation_data = None
    
    for conversation in conversations:
        # Get other participant(s)
        other_participant = conversation.get_other_participant(request.user)
        
        if not other_participant:
            continue
        
        # Get profile picture URL
        participant_avatar = 'https://placehold.co/50x50/c2c2c2/1f1f1f?text=User'
        if hasattr(other_participant, 'profile') and other_participant.profile.profile_picture:
            try:
                participant_avatar = other_participant.profile.profile_picture.url
            except:
                pass
        
        # Get online status
        try:
            status = UserOnlineStatus.objects.get(user=other_participant)
            is_online = status.is_online
            last_seen = status.last_seen
        except UserOnlineStatus.DoesNotExist:
            is_online = False
            last_seen = None
        
        # Get last message
        try:
            last_message = conversation.messages.latest('timestamp')
            last_message_content = last_message.content[:100] if last_message.content else '[No message]'
            last_message_sender_id = last_message.sender_id
            last_message_time = last_message.timestamp
        except Message.DoesNotExist:
            last_message_content = 'Start conversation'
            last_message_sender_id = None
            last_message_time = conversation.start_date
        
        conversation_dict = {
            'id': conversation.id,
            'participant_id': other_participant.id,
            'participant_name': other_participant.get_full_name() or other_participant.username,
            'participant_username': other_participant.username,
            'participant_avatar': participant_avatar,
            'is_online': is_online,
            'last_seen': last_seen,
            'last_message': {
                'content': last_message_content,
                'sender_id': last_message_sender_id,
                'timestamp': last_message_time,
                'is_own_message': last_message_sender_id == request.user.id if last_message_sender_id else False
            },
            'unread_count': conversation.unread_count,
            'listing': conversation.listing,
            'listing_title': conversation.listing.title if conversation.listing else None,
            'listing_id': conversation.listing.id if conversation.listing else None,
            'created_at': conversation.start_date
        }
        
        conversations_data.append(conversation_dict)
        
        # Check if this is the conversation to open
        if open_conversation_id and str(conversation.id) == open_conversation_id:
            open_conversation_data = conversation_dict
    
    # Calculate total unread count
    total_unread_count = sum(conv['unread_count'] for conv in conversations_data)
    
    return render(request, 'chats/inbox.html', {
        'conversations': conversations_data,
        'user': request.user,
        'open_conversation': open_conversation_data,
        'total_unread_count': total_unread_count
    })

@login_required
def get_unread_count(request):
    """Get total unread messages count"""
    total_unread = Message.objects.filter(
        conversation__participants=request.user,
        is_read=False
    ).exclude(sender=request.user).count()
    
    return JsonResponse({
        'success': True,
        'total_unread': total_unread
    })


# API VIEWS
@login_required
def api_get_online_users(request):
    """API endpoint to get list of online users"""
    try:
        online_user_ids = get_online_user_ids()
        # Remove current user from the list
        if request.user.id in online_user_ids:
            online_user_ids.remove(request.user.id)
        
        return JsonResponse({
            'online_users': list(online_user_ids),
            'success': True
        })
    except Exception as e:
        logger.error(f"Error in api_get_online_users: {e}")
        return JsonResponse({'online_users': [], 'success': False})


@login_required
def search_users(request):
    """Search users for new conversation"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'users': [], 'success': True})
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    try:
        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        ).exclude(id=request.user.id).filter(is_active=True)[:20]
        
        users_data = []
        for user in users:
            avatar_url = 'https://placehold.co/50x50/c2c2c2/1f1f1f?text=User'
            if hasattr(user, 'profile'):
                try:
                    if user.profile.profile_picture:
                        avatar_url = request.build_absolute_uri(user.profile.profile_picture.url)
                except:
                    pass
            
            users_data.append({
                'id': user.id,
                'username': user.username,
                'name': user.get_full_name() or user.username,
                'avatar': avatar_url,
                'email': user.email
            })
        
        return JsonResponse({'success': True, 'users': users_data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def my_listings(request):
    """Get user's listings for conversation context"""
    try:
        from listings.models import Listing
        
        listings = Listing.objects.filter(
            user=request.user
        ).select_related('category').order_by('-created_at')[:20]
        
        listings_data = []
        for listing in listings:
            image_url = ''
            try:
                if hasattr(listing, 'get_image_url'):
                    image_url = listing.get_image_url()
                elif hasattr(listing, 'image') and listing.image:
                    image_url = request.build_absolute_uri(listing.image.url)
                elif hasattr(listing, 'images') and listing.images.exists():
                    image_url = request.build_absolute_uri(listing.images.first().image.url)
            except:
                pass
            
            listings_data.append({
                'id': listing.id,
                'title': listing.title,
                'price': listing.price,
                'image': image_url
            })
        
        return JsonResponse({'listings': listings_data})
        
    except Exception as e:
        return JsonResponse({'listings': []})



# In views.py, update the conversation_detail function
@login_required
def conversation_detail(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk, participants=request.user)
    
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('ajax') == 'true'
    
    # Mark messages as read when viewing the conversation
    unread_messages = Message.objects.filter(
        conversation=conversation
    ).exclude(
        sender=request.user
    ).filter(
        is_read=False
    )
    
    unread_messages.update(is_read=True)
    
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.save()
            
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message_id': message.id,
                    'message': {
                        'id': message.id,
                        'content': message.content,
                        'timestamp': message.timestamp.isoformat(),
                        'sender': message.sender.username,
                        'sender_avatar': message.sender.get_profile_picture_url() if hasattr(message.sender, 'get_profile_picture_url') else 'https://placehold.co/32x32/c2c2c2/1f1f1f?text=User',
                        'is_own_message': True,
                        'is_read': message.is_read
                    }
                })
            return redirect('conversation-detail', pk=pk)
    
    # GET request handling
    messages = conversation.messages.all().select_related('sender')
    form = MessageForm()
    
    # Get other participant
    other_participants = conversation.participants.exclude(id=request.user.id)
    other_participant = other_participants.first() if other_participants.exists() else None
    
    # Handle AJAX requests
    if is_ajax:
        messages_data = []
        for msg in messages:
            messages_data.append({
                'id': msg.id,
                'sender': msg.sender.username,
                'sender_avatar': msg.sender.get_profile_picture_url() if hasattr(msg.sender, 'get_profile_picture_url') else 'https://placehold.co/32x32/c2c2c2/1f1f1f?text=User',
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                'is_read': msg.is_read,
                'is_own_message': msg.sender == request.user
            })
        
        # Check for new messages if polling
        last_message_id = request.GET.get('last_id')
        if last_message_id:
            try:
                new_messages = messages.filter(id__gt=int(last_message_id))
                new_messages_data = []
                for msg in new_messages:
                    new_messages_data.append({
                        'id': msg.id,
                        'sender': msg.sender.username,
                        'sender_avatar': msg.sender.get_profile_picture_url() if hasattr(msg.sender, 'get_profile_picture_url') else 'https://placehold.co/32x32/c2c2c2/1f1f1f?text=User',
                        'content': msg.content,
                        'timestamp': msg.timestamp.isoformat(),
                        'is_read': msg.is_read,
                        'is_own_message': msg.sender == request.user
                    })
                return JsonResponse({'new_messages': new_messages_data})
            except ValueError:
                pass
        
        return JsonResponse({
            'success': True,
            'conversation_id': conversation.id,
            'messages': messages_data,
            'participants': [{
                'id': user.id,
                'username': user.username,
                'full_name': user.get_full_name() or user.username,
                'avatar': user.get_profile_picture_url() if hasattr(user, 'get_profile_picture_url') else 'https://placehold.co/50x50/c2c2c2/1f1f1f?text=User',
                'is_current_user': user == request.user
            } for user in conversation.participants.all()],
            'listing': {
                'title': conversation.listing.title if conversation.listing else None,
                'price': conversation.listing.price if conversation.listing else None,
                'image': conversation.listing.get_image_url() if conversation.listing and hasattr(conversation.listing, 'get_image_url') else None,
                'url': f"/listings/{conversation.listing.id}/" if conversation.listing else None
            } if conversation.listing else None
        })
    
    return render(request, 'chats/conversation.html', {
        'conversation': conversation,
        'messages': messages,
        'form': form,
        'other_participants': other_participants
    })

@login_required
def start_conversation(request, listing_id, recipient_id):
    from listings.models import Listing
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    listing = get_object_or_404(Listing, pk=listing_id)
    recipient = get_object_or_404(User, pk=recipient_id)
    
    # Check if conversation already exists
    conversation = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=recipient
    ).filter(
        listing=listing
    ).first()
    
    if not conversation:
        conversation = Conversation.objects.create(listing=listing)
        conversation.participants.add(request.user, recipient)
        conversation.save()
    
    # Redirect to inbox with conversation ID as parameter
    return redirect(f'/chats/?open={conversation.pk}')


@login_required
def unread_messages_count(request):
    """API endpoint to get unread messages count"""
    unread_count = Message.objects.filter(
        conversation__participants=request.user
    ).exclude(
        sender=request.user
    ).filter(
        is_read=False
    ).count()
    
    # Also return per-conversation counts for UI updates
    conversations = Conversation.objects.filter(participants=request.user).annotate(
        unread_count=Count(
            'messages',
            filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user)
        )
    ).values('id', 'unread_count')
    
    return JsonResponse({
        'count': unread_count,
        'conversations': list(conversations)
    })


@login_required
@require_POST
def mark_messages_read(request, conversation_id):
    """Mark all messages in a conversation as read"""
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    
    # Mark all unread messages from other participants as read
    Message.objects.filter(
        conversation=conversation
    ).exclude(
        sender=request.user
    ).filter(
        is_read=False
    ).update(is_read=True)
    
    # Update global unread count
    global_unread_count = Message.objects.filter(
        conversation__participants=request.user
    ).exclude(
        sender=request.user
    ).filter(
        is_read=False
    ).count()
    
    return JsonResponse({
        'success': True,
        'unread_count': global_unread_count
    })


@login_required
@csrf_exempt
def delete_message(request, message_id):
    """Delete a message (soft delete)"""
    try:
        message = get_object_or_404(Message, id=message_id, sender=request.user)
        message.is_deleted = True
        message.content = '[Message deleted]'
        message.save(update_fields=['is_deleted', 'content'])
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
def send_typing_indicator(request, conversation_id):
    """Send typing indicator to other participants"""
    try:
        conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
        
        # Store typing indicator in cache or database
        from django.core.cache import cache
        
        cache_key = f'typing_{conversation_id}_{request.user.id}'
        cache.set(cache_key, True, timeout=5)  # Typing indicator lasts 5 seconds
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
@login_required
def check_typing(request, conversation_id):
    """Check if other participants are typing"""
    try:
        conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
        
        # Use Django cache
        from django.core.cache import cache
        
        # Check all other participants
        other_participants = conversation.participants.exclude(id=request.user.id)
        typing_users = []
        
        for participant in other_participants:
            cache_key = f'typing_{conversation_id}_{participant.id}'
            if cache.get(cache_key):
                typing_users.append({
                    'id': participant.id,
                    'name': participant.get_full_name() or participant.username
                })
        
        return JsonResponse({
            'typing': len(typing_users) > 0,
            'users': typing_users,
            'user_name': typing_users[0]['name'] if typing_users else '',
            'is_self': False
        })
        
    except Exception as e:
        # Return a safe response on error
        return JsonResponse({
            'typing': False,
            'users': [],
            'user_name': '',
            'is_self': False
        })

@login_required
def check_online_status(request, conversation_id):
    """Check online status of other participants"""
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    other_participants = conversation.participants.exclude(id=request.user.id)
    status_data = []
    
    for participant in other_participants:
        # Check last activity (you need to implement this in your User model)
        last_active = getattr(participant, 'last_active', None)
        
        if last_active:
            time_diff = timezone.now() - last_active
            is_online = time_diff < timedelta(minutes=5)
            last_seen = format_last_seen(time_diff)
        else:
            is_online = False
            last_seen = 'Unknown'
        
        status_data.append({
            'id': participant.id,
            'online': is_online,
            'last_seen': last_seen
        })
    
    return JsonResponse({
        'participants': status_data,
        'online': any(p['online'] for p in status_data)
    })





from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import uuid
from datetime import timedelta


# ===== ADD THIS NEW FUNCTION FOR MESSAGE STATUS UPDATES =====
@login_required
def get_message_status(request, conversation_id):
    """Get read status of sent messages in a conversation"""
    try:
        conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
        
        # Get messages sent by current user in this conversation
        messages = Message.objects.filter(
            conversation=conversation,
            sender=request.user
        ).order_by('-timestamp')[:50]
        
        status_data = {}
        for msg in messages:
            status_data[msg.id] = {
                'id': msg.id,
                'is_read': msg.is_read,
                'read_at': msg.read_at.isoformat() if hasattr(msg, 'read_at') and msg.read_at else None,
                'status': 'read' if msg.is_read else 'delivered' if msg.timestamp < timezone.now() - timezone.timedelta(seconds=5) else 'sent'
            }
        
        return JsonResponse({
            'success': True,
            'status_data': status_data,
            'last_checked': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting message status: {e}")
        return JsonResponse({'success': False, 'error': str(e)})
    
# Add at the top of views.py
import logging
logger = logging.getLogger(__name__)

@login_required
@csrf_exempt
def send_message_api(request):
    """API endpoint for sending messages via AJAX - FIXED"""
    try:
        # Handle both JSON and form data
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                data = {}
        else:
            data = request.POST
        
        logger.info(f"Message send attempt - data: {data}, files: {list(request.FILES.keys())}")
        
        recipient_id = data.get('recipient_id') or data.get('recipient')
        message_content = data.get('message') or data.get('content', '').strip()
        conversation_id = data.get('conversation_id')
        
        # Check if we have either message or files
        if not message_content and not request.FILES:
            return JsonResponse({'success': False, 'error': 'Message or attachment is required'}, status=400)
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        conversation = None
        
        # If conversation_id provided, use it
        if conversation_id:
            try:
                conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
                logger.info(f"Using existing conversation: {conversation_id}")
            except Exception as e:
                logger.error(f"Error finding conversation {conversation_id}: {e}")
                return JsonResponse({'success': False, 'error': 'Conversation not found'}, status=404)
        
        # If no conversation_id but recipient_id, find/create conversation
        elif recipient_id:
            try:
                recipient = get_object_or_404(User, id=recipient_id)
                
                # Find existing conversation without listing
                conversation = Conversation.objects.filter(
                    participants=request.user
                ).filter(
                    participants=recipient
                ).filter(
                    listing__isnull=True
                ).first()
                
                if not conversation:
                    conversation = Conversation.objects.create()
                    conversation.participants.add(request.user, recipient)
                    conversation.save()
                    logger.info(f"Created new conversation: {conversation.id}")
                
            except Exception as e:
                logger.error(f"Error with recipient {recipient_id}: {e}")
                return JsonResponse({'success': False, 'error': 'Recipient not found'}, status=404)
        else:
            return JsonResponse({'success': False, 'error': 'Either recipient or conversation ID required'}, status=400)
        
        # Create the message
        try:
            message = Message.objects.create(
                conversation=conversation,
                sender=request.user,
                content=message_content or '[Attachment]'
            )
            logger.info(f"Message created: {message.id}")
            
            # Handle attachments if any
            attachments_data = []
            if request.FILES:
                for key in request.FILES:
                    file = request.FILES[key]
                    
                    # Generate unique filename
                    file_ext = file.name.split('.')[-1] if '.' in file.name else 'file'
                    filename = f"attachments/{uuid.uuid4()}.{file_ext}"
                    
                    # Save file
                    saved_path = default_storage.save(filename, ContentFile(file.read()))
                    file_url = default_storage.url(saved_path)
                    
                    attachments_data.append({
                        'name': file.name,
                        'url': file_url,
                        'type': file.content_type,
                        'size': file.size,
                        'filename': filename
                    })
                    
                    logger.info(f"Attachment saved: {filename}")
            
            # Get user profile picture URL
            sender_avatar = 'https://placehold.co/32x32/c2c2c2/1f1f1f?text=You'
            if hasattr(request.user, 'profile'):
                try:
                    if request.user.profile.profile_picture and hasattr(request.user.profile.profile_picture, 'url'):
                        sender_avatar = request.user.profile.profile_picture.url
                except Exception as e:
                    logger.warning(f"Could not get profile picture: {e}")
            
            response_data = {
                'success': True,
                'conversation_id': conversation.id,
                'message_id': message.id,
                'message': {
                    'id': message.id,
                    'content': message.content,
                    'timestamp': message.timestamp.isoformat(),
                    'sender': request.user.username,
                    'sender_avatar': sender_avatar,
                    'is_own_message': True,
                    'is_read': False,
                    'status': 'sent'  # Initial status
                }
            }
            
            # Add attachments data if any
            if attachments_data:
                response_data['message']['attachments'] = attachments_data
            
            return JsonResponse(response_data)
            
        except Exception as e:
            logger.error(f"Error creating message: {e}")
            return JsonResponse({'success': False, 'error': 'Failed to create message'}, status=500)
            
    except Exception as e:
        logger.error(f"Unexpected error in send_message_api: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# Fix get_new_messages function
@login_required
def get_new_messages(request, conversation_id):
    """Get new messages since last message ID"""
    try:
        conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
        
        # Get last message ID from request
        last_message_id = request.GET.get('last_id', '0')
        try:
            last_message_id = int(last_message_id)
        except ValueError:
            last_message_id = 0
        
        # Get new messages
        new_messages = Message.objects.filter(
            conversation=conversation,
            id__gt=last_message_id
        ).select_related('sender').order_by('timestamp')
        
        messages_data = []
        for msg in new_messages:
            # Get sender avatar
            sender_avatar = 'https://placehold.co/32x32/c2c2c2/1f1f1f?text=User'
            if hasattr(msg.sender, 'profile'):
                try:
                    if msg.sender.profile.profile_picture and hasattr(msg.sender.profile.profile_picture, 'url'):
                        sender_avatar = msg.sender.profile.profile_picture.url
                except Exception:
                    pass
            
            messages_data.append({
                'id': msg.id,
                'sender': msg.sender.username,
                'sender_avatar': sender_avatar,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                'is_read': msg.is_read,
                'is_own_message': msg.sender == request.user
            })
        
        return JsonResponse({
            'success': True,
            'conversation_id': conversation_id,
            'new_messages': messages_data,
            'last_message_id': new_messages.last().id if new_messages.exists() else last_message_id
        })
        
    except Exception as e:
        logger.error(f"Error in get_new_messages: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'new_messages': []
        }, status=500)

# Fix conversations_list endpoint
@login_required
def conversations_list(request):
    """Get conversations list with detailed information"""
    try:
        conversations = Conversation.objects.filter(
            participants=request.user
        ).annotate(
            unread_count=Count(
                'messages',
                filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user)
            ),
            last_message_time=Subquery(
                Message.objects.filter(
                    conversation=OuterRef('pk')
                ).order_by('-timestamp').values('timestamp')[:1]
            ),
            last_message_content=Subquery(
                Message.objects.filter(
                    conversation=OuterRef('pk')
                ).order_by('-timestamp').values('content')[:1]
            ),
            last_message_sender_id=Subquery(
                Message.objects.filter(
                    conversation=OuterRef('pk')
                ).order_by('-timestamp').values('sender')[:1]
            )
        ).order_by('-last_message_time')[:50]
        
        conversations_data = []
        for conversation in conversations:
            # Get other participant
            other_participant = conversation.participants.exclude(id=request.user.id).first()
            
            # Get participant avatar
            participant_avatar = 'https://placehold.co/48x48/c2c2c2/1f1f1f?text=User'
            if other_participant and hasattr(other_participant, 'profile'):
                try:
                    if other_participant.profile.profile_picture and hasattr(other_participant.profile.profile_picture, 'url'):
                        participant_avatar = other_participant.profile.profile_picture.url
                except Exception:
                    pass
            
            conversations_data.append({
                'id': conversation.id,
                'participant_id': other_participant.id if other_participant else None,
                'participant_username': other_participant.username if other_participant else '',
                'participant_name': other_participant.get_full_name() or other_participant.username if other_participant else '',
                'participant_avatar': participant_avatar,
                'last_message_content': conversation.last_message_content or '',
                'last_message_sender_id': conversation.last_message_sender_id,
                'last_message_time': conversation.last_message_time.isoformat() if conversation.last_message_time else conversation.start_date.isoformat(),
                'unread_count': conversation.unread_count,
                'listing_id': conversation.listing.id if conversation.listing else None,
                'listing_title': conversation.listing.title if conversation.listing else ''
            })
        
        return JsonResponse({
            'success': True,
            'conversations': conversations_data
        })
        
    except Exception as e:
        logger.error(f"Error in conversations_list: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'conversations': []
        })
    
@login_required
@csrf_exempt
def send_message_with_attachments(request):
    """Send message with attachments"""
    try:
        data = request.POST
        recipient_id = data.get('recipient')
        message_content = data.get('message', '').strip()
        listing_id = data.get('listing_id')
        
        if not recipient_id:
            return JsonResponse({'success': False, 'error': 'Recipient required'})
        
        from django.contrib.auth import get_user_model
        from listings.models import Listing
        User = get_user_model()
        
        recipient = get_object_or_404(User, id=recipient_id)
        listing = get_object_or_404(Listing, id=listing_id) if listing_id else None
        
        # Find or create conversation
        conversation = Conversation.objects.filter(
            participants=request.user
        ).filter(
            participants=recipient
        )
        
        if listing:
            conversation = conversation.filter(listing=listing).first()
        else:
            conversation = conversation.filter(listing__isnull=True).first()
        
        if not conversation:
            conversation = Conversation.objects.create(listing=listing)
            conversation.participants.add(request.user, recipient)
            conversation.save()
        
        # Create message
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=message_content
        )
        
        # Handle attachments
        attachments_data = []
        for key in request.FILES:
            if key.startswith('attachment_'):
                file = request.FILES[key]
                
                # Generate unique filename
                file_ext = file.name.split('.')[-1]
                filename = f"attachments/{uuid.uuid4()}.{file_ext}"
                
                # Save file
                saved_path = default_storage.save(filename, ContentFile(file.read()))
                file_url = default_storage.url(saved_path)
                
                # Create attachment record (you'll need an Attachment model)
                # For now, we'll store in message metadata
                attachments_data.append({
                    'name': file.name,
                    'url': file_url,
                    'type': file.content_type,
                    'size': file.size
                })
        
        # Update conversation last message time
        conversation.last_message_time = timezone.now()
        conversation.save(update_fields=['last_message_time'])
        
        # Prepare response
        response_data = {
            'success': True,
            'conversation_id': conversation.id,
            'conversation_url': f'/chats/conversation/{conversation.id}/',
            'message_id': message.id,
            'message': {
                'id': message.id,
                'content': message.content,
                'timestamp': message.timestamp.isoformat(),
                'sender': request.user.username,
                'attachments': attachments_data
            }
        }
        
        # Update unread count
        unread_count = Message.objects.filter(
            conversation__participants=request.user
        ).exclude(
            sender=request.user
        ).filter(
            is_read=False
        ).count()
        response_data['unread_count'] = unread_count
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
def initiate_call(request):
    """Initiate a voice or video call"""
    try:
        data = json.loads(request.body)
        recipient_id = data.get('recipient_id')
        call_type = data.get('call_type', 'voice')
        call_id = data.get('call_id')
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        recipient = get_object_or_404(User, id=recipient_id)
        
        # Create call record (you'll need a Call model)
        # For now, return a mock response
        return JsonResponse({
            'success': True,
            'call_id': call_id,
            'call_type': call_type,
            'recipient_name': recipient.get_full_name() or recipient.username,
            'call_url': f'/calls/{call_id}/',  # This would be your WebRTC signaling URL
            'message': f'Call request sent to {recipient.username}'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_attachments(request, conversation_id):
    """Get all attachments in a conversation"""
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    
    # Get messages with attachments
    messages_with_attachments = Message.objects.filter(
        conversation=conversation
    ).exclude(
        attachments=None
    ).order_by('-timestamp')
    
    attachments_data = []
    for message in messages_with_attachments:
        # Parse attachments from message (you'll need to implement this based on your storage)
        pass
    
    return JsonResponse({'attachments': attachments_data})


@login_required
def delete_conversation(request, conversation_id):
    """Soft delete a conversation"""
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    
    # Mark as archived (you'll need an archived field)
    conversation.is_archived = True
    conversation.save(update_fields=['is_archived'])
    
    return JsonResponse({'success': True, 'message': 'Conversation archived'})


@login_required
def mute_conversation(request, conversation_id):
    """Mute notifications for a conversation"""
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    
    # Toggle mute status (you'll need a muted field)
    conversation.muted = not conversation.muted
    conversation.save(update_fields=['muted'])
    
    status = 'muted' if conversation.muted else 'unmuted'
    return JsonResponse({'success': True, 'status': status})


@login_required
def block_user(request, user_id):
    """Block a user from messaging"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    user_to_block = get_object_or_404(User, id=user_id)
    
    # Add to blocked users (you'll need a blocking system)
    # For now, just return success
    return JsonResponse({
        'success': True,
        'message': f'Blocked {user_to_block.username}',
        'blocked_user_id': user_id
    })


from django.views.decorators.csrf import csrf_exempt
import json
from datetime import datetime

@login_required
@csrf_exempt
def send_call_offer(request):
    """Handle WebRTC call offer"""
    try:
        data = json.loads(request.body)
        recipient_id = data.get('recipient_id')
        call_type = data.get('call_type')
        offer = data.get('offer')
        call_id = data.get('call_id')
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        recipient = get_object_or_404(User, id=recipient_id)
        
        # Store call offer in cache
        from django.core.cache import cache
        cache_key = f'call_offer_{call_id}'
        cache.set(cache_key, {
            'caller_id': request.user.id,
            'caller_name': request.user.get_full_name() or request.user.username,
            'call_type': call_type,
            'offer': offer,
            'timestamp': datetime.now().isoformat()
        }, timeout=60)  # Store for 60 seconds
        
        # Create notification for recipient
        create_call_notification(recipient, request.user, call_id, call_type)
        
        return JsonResponse({
            'success': True,
            'call_id': call_id,
            'message': 'Call offer sent'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_call_answer(request, call_id):
    """Get call answer from recipient"""
    from django.core.cache import cache
    
    # Check for answer
    answer_key = f'call_answer_{call_id}'
    answer = cache.get(answer_key)
    
    # Check if call was declined or ended
    end_key = f'call_end_{call_id}'
    call_ended = cache.get(end_key)
    
    if call_ended:
        cache.delete(answer_key)
        cache.delete(end_key)
        return JsonResponse({'ended': True})
    
    if answer:
        cache.delete(answer_key)
        return JsonResponse({'answer': answer})
    
    return JsonResponse({'answer': None})


@login_required
@csrf_exempt
def send_call_answer(request):
    """Send call answer"""
    try:
        data = json.loads(request.body)
        call_id = data.get('call_id')
        answer = data.get('answer')
        
        from django.core.cache import cache
        
        # Store answer in cache
        answer_key = f'call_answer_{call_id}'
        cache.set(answer_key, answer, timeout=60)
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
def send_ice_candidate(request):
    """Send ICE candidate"""
    try:
        data = json.loads(request.body)
        call_id = data.get('call_id')
        candidate = data.get('candidate')
        
        from django.core.cache import cache
        
        # Store ICE candidate
        ice_key = f'call_ice_{call_id}_{request.user.id}'
        candidates = cache.get(ice_key, [])
        candidates.append(candidate)
        cache.set(ice_key, candidates, timeout=60)
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_ice_candidates(request, call_id):
    """Get ICE candidates for a call"""
    from django.core.cache import cache
    
    # Get other user's ICE candidates
    other_user_id = get_other_call_participant(call_id, request.user.id)
    if not other_user_id:
        return JsonResponse({'candidates': []})
    
    ice_key = f'call_ice_{call_id}_{other_user_id}'
    candidates = cache.get(ice_key, [])
    
    # Clear after retrieving
    cache.delete(ice_key)
    
    return JsonResponse({'candidates': candidates})


@login_required
@csrf_exempt
def end_call(request):
    """End a call"""
    try:
        data = json.loads(request.body)
        call_id = data.get('call_id')
        
        from django.core.cache import cache
        
        # Mark call as ended
        end_key = f'call_end_{call_id}'
        cache.set(end_key, True, timeout=60)
        
        # Clear call data
        cache.delete(f'call_offer_{call_id}')
        cache.delete(f'call_answer_{call_id}')
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def create_call_notification(recipient, caller, call_id, call_type):
    """Create a call notification"""
    # This would integrate with your notifications system
    # For now, we'll store in cache
    from django.core.cache import cache
    
    notification_key = f'call_notification_{recipient.id}_{call_id}'
    cache.set(notification_key, {
        'caller_id': caller.id,
        'caller_name': caller.get_full_name() or caller.username,
        'call_type': call_type,
        'call_id': call_id,
        'timestamp': datetime.now().isoformat()
    }, timeout=60)
    
    # In production, you would:
    # 1. Create a Notification object
    # 2. Send push notification
    # 3. Update UI via WebSocket


def get_other_call_participant(call_id, user_id):
    """Get the other participant in a call"""
    from django.core.cache import cache
    
    # Get call offer to find caller
    offer_key = f'call_offer_{call_id}'
    offer_data = cache.get(offer_key)
    
    if offer_data:
        if offer_data['caller_id'] == user_id:
            # This user is the caller, need to find who answered
            answer_key = f'call_answer_{call_id}'
            if cache.get(answer_key):
                # The answer would be stored by the recipient
                # We need a way to track who answered
                pass
        else:
            # This user is the recipient, caller is other participant
            return offer_data['caller_id']
    
    return None

@login_required
def debug_online_users(request):
    """Debug view to check online users functionality"""
    online_user_ids = get_online_user_ids()
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    online_users = User.objects.filter(id__in=online_user_ids)
    
    return JsonResponse({
        'online_user_ids': list(online_user_ids),
        'online_users': [
            {
                'id': user.id,
                'username': user.username,
                'name': user.get_full_name(),
                'is_current': user.id == request.user.id
            }
            for user in online_users
        ],
        'current_user_id': request.user.id,
        'total_sessions': len(online_user_ids)
    })

# Add these functions to your existing views.py

@login_required
def update_online_status(request):
    """Update user's online status"""
    try:
        data = json.loads(request.body)
        is_online = data.get('is_online', True)
        
        status, created = UserOnlineStatus.objects.get_or_create(user=request.user)
        status.is_online = is_online
        status.last_active = timezone.now()
        
        if is_online:
            status.last_seen = timezone.now()
        
        status.save(update_fields=['is_online', 'last_active', 'last_seen'])
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def get_conversation_status(request, conversation_id):
    """Get conversation status including online status"""
    try:
        conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
        other_participant = conversation.get_other_participant(request.user)
        
        if not other_participant:
            return JsonResponse({'success': False, 'error': 'Participant not found'})
        
        # Get online status
        try:
            status = UserOnlineStatus.objects.get(user=other_participant)
            is_online = status.is_online
            last_seen = status.last_seen
        except UserOnlineStatus.DoesNotExist:
            is_online = False
            last_seen = None
        
        # Get unread count
        unread_count = Message.objects.filter(
            conversation=conversation,
            is_read=False
        ).exclude(sender=request.user).count()
        
        return JsonResponse({
            'success': True,
            'is_online': is_online,
            'last_seen': last_seen.isoformat() if last_seen else None,
            'unread_count': unread_count,
            'participant_info': {
                'id': other_participant.id,
                'name': other_participant.get_full_name() or other_participant.username,
                'username': other_participant.username,
                'avatar': other_participant.profile.profile_picture.url if hasattr(other_participant, 'profile') and other_participant.profile.profile_picture else None
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def group_conversations(request):
    """Group conversations by participant"""
    try:
        conversations = Conversation.objects.filter(
            participants=request.user,
            is_archived=False
        ).annotate(
            unread_count=Count(
                'messages',
                filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user)
            ),
            last_message_time=Max('messages__timestamp')
        ).order_by('-last_message_time')
        
        # Group by participant
        grouped = {}
        for conv in conversations:
            other_participant = conv.get_other_participant(request.user)
            if not other_participant:
                continue
                
            participant_id = other_participant.id
            if participant_id not in grouped:
                grouped[participant_id] = {
                    'participant': {
                        'id': other_participant.id,
                        'name': other_participant.get_full_name() or other_participant.username,
                        'username': other_participant.username,
                        'avatar': other_participant.profile.profile_picture.url if hasattr(other_participant, 'profile') and other_participant.profile.profile_picture else None
                    },
                    'conversations': [],
                    'total_unread': 0
                }
            
            # Get latest message
            try:
                last_message = conv.messages.latest('timestamp')
                last_message_content = last_message.content
                last_message_is_own = last_message.sender == request.user
            except Message.DoesNotExist:
                last_message_content = 'Start conversation'
                last_message_is_own = False
            
            grouped[participant_id]['conversations'].append({
                'id': conv.id,
                'listing_title': conv.listing.title if conv.listing else None,
                'listing_id': conv.listing.id if conv.listing else None,
                'last_message': {
                    'content': last_message_content,
                    'is_own': last_message_is_own,
                    'timestamp': conv.last_message_time.isoformat() if conv.last_message_time else conv.start_date.isoformat()
                },
                'unread_count': conv.unread_count
            })
            
            grouped[participant_id]['total_unread'] += conv.unread_count
        
        # Convert to list and sort by last message time
        result = list(grouped.values())
        result.sort(key=lambda x: max(
            [c['last_message']['timestamp'] for c in x['conversations']]
        ), reverse=True)
        
        return JsonResponse({
            'success': True,
            'grouped_conversations': result
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})