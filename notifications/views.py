
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Notification, NotificationPreference
from .forms import NotificationPreferenceForm

@login_required
def notification_list(request):
    """View all notifications for the user"""
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    
    # Get unread count - use a fresh query to avoid issues
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    
    # Handle AJAX requests for real-time updates
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        recent_notifications = notifications[:5]
        
        notifications_data = []
        for notification in recent_notifications:
            notifications_data.append({
                'id': notification.id,
                'title': notification.title,
                'message': notification.message,
                'type': notification.notification_type,
                'is_read': notification.is_read,
                'time_since': notification.time_since,
                'action_url': notification.action_url,
                'action_text': notification.action_text,
            })
        
        return JsonResponse({
            'unread_count': unread_count,
            'notifications': notifications_data
        })
    
    # Filter by type if specified
    notification_type = request.GET.get('type')
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)
    
    # Filter by read status
    read_status = request.GET.get('read')
    if read_status == 'unread':
        notifications = notifications.filter(is_read=False)
    elif read_status == 'read':
        notifications = notifications.filter(is_read=True)
    
    # Pagination
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'notifications/notification_list.html', {
        'page_obj': page_obj,
        'unread_count': unread_count,
        'unread_notifications_count': unread_count,  # For base.html compatibility
        'notification_types': Notification.NOTIFICATION_TYPES,
        'selected_type': notification_type,
        'selected_status': read_status,
    })

@login_required
@require_POST
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.mark_as_read()
    notification.is_read = True
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('notifications')

@login_required
@require_POST
def mark_all_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('notifications')

@login_required
@require_POST
def delete_notification(request, notification_id):
    """Delete a notification"""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('notifications')

@login_required
@require_POST
def clear_all_notifications(request):
    """Clear all notifications"""
    Notification.objects.filter(recipient=request.user).delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('notifications')

@login_required
def notification_preferences(request):
    """Manage notification preferences"""
    preferences, created = NotificationPreference.objects.get_or_create(user=request.user)
    
    # Get unread count for base template
    unread_notifications_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    
    if request.method == 'POST':
        form = NotificationPreferenceForm(request.POST, instance=preferences)
        if form.is_valid():
            form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('notification-preferences')
    else:
        form = NotificationPreferenceForm(instance=preferences)
    
    return render(request, 'notifications/preferences.html', {
        'form': form,
        'unread_notifications_count': unread_notifications_count
    })

@login_required
def get_unread_count(request):
    """API endpoint to get unread notification count"""
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'unread_count': unread_count})
