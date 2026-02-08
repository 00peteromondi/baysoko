from .models import DeliveryNotification


def delivery_user_context(request):
    """Expose seller/delivery flags and unread notification count to templates.

    - `is_seller`: True if user owns at least one Store (set by middleware too)
    - `is_delivery_person`: True if user has a delivery_person relation
    - `unread_notifications_count`: number of unread DeliveryNotification for user
    """
    user = getattr(request, 'user', None)
    is_seller = getattr(request, 'is_seller', False) if user and getattr(user, 'is_authenticated', False) else False
    is_delivery_person = getattr(request, 'is_delivery_person', False) if user and getattr(user, 'is_authenticated', False) else False
    unread_notifications_count = 0
    try:
        if user and getattr(user, 'is_authenticated', False):
            unread_notifications_count = DeliveryNotification.objects.filter(user=user, is_read=False).count()
    except Exception:
        unread_notifications_count = 0

    return {
        'is_seller': is_seller,
        'is_delivery_person': is_delivery_person,
        'unread_notifications_count': unread_notifications_count,
    }


from django.utils import timezone
from datetime import timedelta
from .models import DeliveryRequest, DeliveryPerson
from django.db.models import Count, Sum, Q

def delivery_stats(request):
    """Add delivery statistics to template context"""
    if not request.user.is_authenticated:
        return {}
    
    try:
        user = request.user
        
        # Get time ranges
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Base queryset
        deliveries = DeliveryRequest.objects.all()
        
        # Filter by user permissions
        if hasattr(user, 'stores') and not user.is_staff:
            user_stores = user.stores.all()
            deliveries = deliveries.filter(metadata__store_id__in=user_stores.values_list('id', flat=True))
        elif hasattr(user, 'delivery_person') and not user.is_staff:
            deliveries = deliveries.filter(delivery_person=user.delivery_person)
        
        # Today's stats
        today_deliveries = deliveries.filter(created_at__date=today)
        today_stats = {
            'total': today_deliveries.count(),
            'delivered': today_deliveries.filter(status='delivered').count(),
            'pending': today_deliveries.filter(status='pending').count(),
            'in_transit': today_deliveries.filter(status='in_transit').count(),
            'revenue': today_deliveries.filter(status='delivered').aggregate(
                Sum('delivery_fee')
            )['delivery_fee__sum'] or 0
        }
        
        # Weekly stats
        weekly_stats = {
            'total': deliveries.filter(created_at__date__gte=week_ago).count(),
            'revenue': deliveries.filter(
                created_at__date__gte=week_ago,
                status='delivered'
            ).aggregate(Sum('delivery_fee'))['delivery_fee__sum'] or 0
        }
        
        # Monthly stats
        monthly_stats = {
            'total': deliveries.filter(created_at__date__gte=month_ago).count(),
            'revenue': deliveries.filter(
                created_at__date__gte=month_ago,
                status='delivered'
            ).aggregate(Sum('delivery_fee'))['delivery_fee__sum'] or 0
        }
        
        # Status counts
        status_counts = deliveries.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        # Delivery person stats (for admins)
        driver_stats = {}
        if user.is_staff or user.is_superuser:
            active_drivers = DeliveryPerson.objects.filter(is_active=True).count()
            available_drivers = DeliveryPerson.objects.filter(
                is_active=True,
                current_status='available'
            ).count()
            
            driver_stats = {
                'total': active_drivers,
                'available': available_drivers,
                'busy': active_drivers - available_drivers
            }
        
        return {
            'delivery_stats': {
                'today': today_stats,
                'weekly': weekly_stats,
                'monthly': monthly_stats,
                'status_counts': status_counts,
                'driver_stats': driver_stats
            },
            'is_delivery_person': hasattr(user, 'delivery_person'),
            'is_seller': hasattr(user, 'stores'),
            'has_multiple_stores': hasattr(user, 'stores') and user.stores.count() > 1
        }
        
    except Exception as e:
        # Log error but don't break the page
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in delivery_stats context processor: {e}")
        return {}