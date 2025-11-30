from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Conversation, Message
from .forms import MessageForm


@login_required
def inbox(request):
    conversations = Conversation.objects.filter(participants=request.user).order_by('-start_date')
    
    # Handle AJAX requests for partial updates
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        conversations_data = []
        for conversation in conversations:
            last_message = conversation.messages.last()
            other_participants = conversation.participants.exclude(id=request.user.id)
            
            conversations_data.append({
                'id': conversation.id,
                'participants': [{
                    'username': user.username,
                    'profile_picture': user.get_profile_picture_url() if hasattr(user, 'get_profile_picture_url') else (
                        user.profile.profile_picture.url if getattr(user, 'profile', None) and getattr(user.profile, 'profile_picture', None) else 'https://placehold.co/50x50/c2c2c2/1f1f1f?text=HS'
                    )
                } for user in other_participants],
                'last_message': {
                    'content': last_message.content if last_message else '',
                    'timestamp': last_message.timestamp.isoformat() if last_message else conversation.start_date.isoformat(),
                    'sender': last_message.sender.username if last_message else '',
                    'is_read': last_message.is_read if last_message else True
                },
                'unread_count': conversation.messages.exclude(sender=request.user).filter(is_read=False).count(),
                'listing_title': conversation.listing.title if conversation.listing else None
            })
        
        return JsonResponse({'conversations': conversations_data})
    
    return render(request, 'chats/inbox.html', {'conversations': conversations})

@login_required
def conversation_detail(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk, participants=request.user)
    
    # Mark messages as read when viewing the conversation
    Message.objects.filter(
        conversation=conversation
    ).exclude(
        sender=request.user
    ).filter(
        is_read=False
    ).update(is_read=True)
    
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.save()
            
                
            
            # Return JSON for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': {
                        'content': message.content,
                        'timestamp': message.timestamp.isoformat(),
                        'sender': message.sender.username
                    }
                })
            return redirect('conversation-detail', pk=pk)
    
    # GET request handling
    messages = conversation.messages.all()
    form = MessageForm()
    
    # Handle AJAX requests for message list
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        messages_data = []
        for msg in messages:
            messages_data.append({
                'id': msg.id,
                'sender': msg.sender.username,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                'is_read': msg.is_read,
                'is_own_message': msg.sender == request.user
            })
        
        return JsonResponse({
            'conversation_id': conversation.id,
            'messages': messages_data,
            'participants': [{
                'id': user.id,
                'username': user.username,
                'is_current_user': user == request.user
            } for user in conversation.participants.all()]
        })
    
    return render(request, 'chats/conversation.html', {
        'conversation': conversation,
        'messages': messages,
        'form': form
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
    
    return redirect('conversation-detail', pk=conversation.pk)

@login_required
@require_POST
@csrf_exempt
def send_message_api(request):
    """API endpoint for sending messages via AJAX"""
    try:
        data = json.loads(request.body)
        recipient_id = data.get('recipient')
        message_content = data.get('message')
        listing_id = data.get('listing_id')
        
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
            conversation = conversation.first()
        
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
        
        # Notify recipient
        
        
        return JsonResponse({
            'success': True,
            'conversation_url': f'/conversation/{conversation.id}/',
            'message_id': message.id
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
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
    
    return JsonResponse({'count': unread_count})

@login_required
def mark_messages_read(request, conversation_id):
    """Mark all messages in a conversation as read"""
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    Message.objects.filter(conversation=conversation).exclude(sender=request.user).update(is_read=True)
    
    return JsonResponse({'success': True})
