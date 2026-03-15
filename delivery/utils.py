"""
Utility functions for delivery management
"""
import json
import logging
from decimal import Decimal
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q

logger = logging.getLogger(__name__)


def _normalize_area(text):
    if not text:
        return None
    t = str(text).lower()

    # Known location keywords mapped to canonical area
    keyword_map = {
        'kendubay': 'kendu',
        'kendu bay': 'kendu',
        'kendu-bay': 'kendu',
        'kendu': 'kendu',
        'mbita': 'mbita',
        'oyugis': 'oyugis',
        'suba': 'suba',
        'rodi': 'rodi',
        'ndhiwa': 'ndhiwa',
        'homa bay': 'homabay',
        'homa-bay': 'homabay',
        'homabay': 'homabay',
    }

    # Prefer the earliest matched location keyword (ignoring homabay until no other match)
    best = None
    best_pos = None
    homabay_pos = None

    for keyword, canonical in keyword_map.items():
        pos = t.find(keyword)
        if pos == -1:
            continue
        if canonical == 'homabay':
            if homabay_pos is None or pos < homabay_pos:
                homabay_pos = pos
            continue
        if best_pos is None or pos < best_pos:
            best_pos = pos
            best = canonical

    if best:
        return best

    # Contextual hints for homabay when no specific area was matched
    if 'junction' in t:
        return 'homabay'
    if homabay_pos is not None:
        return 'homabay'

    return None


def _route_fee(origin_area, dest_area):
    if not origin_area or not dest_area:
        return None
    if origin_area == dest_area == 'homabay':
        return Decimal('100.00')
    try:
        from .models import DeliveryRouteRate
        rate = DeliveryRouteRate.objects.filter(
            origin=origin_area,
            destination=dest_area,
            is_active=True
        ).first()
        if rate:
            return Decimal(rate.base_fee)
    except Exception:
        pass

    static_rates = {
        ('homabay', 'mbita'): Decimal('200.00'),
        ('homabay', 'oyugis'): Decimal('200.00'),
        ('homabay', 'kendu'): Decimal('200.00'),
        ('homabay', 'suba'): Decimal('300.00'),
        ('homabay', 'rodi'): Decimal('150.00'),
        ('homabay', 'ndhiwa'): Decimal('200.00'),
        ('kendu', 'oyugis'): Decimal('250.00'),
        ('kendu', 'ndhiwa'): Decimal('250.00'),
        ('mbita', 'rodi'): Decimal('300.00'),
        ('mbita', 'ndhiwa'): Decimal('300.00'),
        ('rodi', 'suba'): Decimal('350.00'),
        ('rodi', 'kendu'): Decimal('200.00'),
        ('rodi', 'oyugis'): Decimal('200.00'),
        ('rodi', 'ndhiwa'): Decimal('250.00'),
        ('oyugis', 'mbita'): Decimal('300.00'),
        ('oyugis', 'suba'): Decimal('350.00'),
        ('oyugis', 'ndhiwa'): Decimal('250.00'),
        ('kendu', 'suba'): Decimal('350.00'),
        ('kendu', 'mbita'): Decimal('300.00'),
        ('ndhiwa', 'suba'): Decimal('300.00'),
        ('mbita', 'suba'): Decimal('200.00'),
    }
    if (origin_area, dest_area) in static_rates:
        return static_rates[(origin_area, dest_area)]
    if (dest_area, origin_area) in static_rates:
        return static_rates[(dest_area, origin_area)]
    return None


def calculate_delivery_fee(weight, service_type=None, zone=None, distance=None, pickup_address=None, recipient_address=None):
    """
    Calculate delivery fee using fixed route pricing with weight surcharge.
    """
    base_fee = Decimal('100.00')

    origin = _normalize_area(pickup_address)
    destination = _normalize_area(recipient_address)
    if not origin and destination:
        # Default origin to homabay when pickup location is missing
        origin = 'homabay'
    route_fee = _route_fee(origin, destination)
    if route_fee:
        base_fee = route_fee

    if zone and hasattr(zone, 'delivery_fee'):
        base_fee = max(base_fee, Decimal(zone.delivery_fee))

    if service_type and hasattr(service_type, 'base_price'):
        base_fee = max(base_fee, Decimal(service_type.base_price))

    if distance and service_type and hasattr(service_type, 'price_per_km'):
        try:
            base_fee += Decimal(service_type.price_per_km) * Decimal(str(distance))
        except Exception:
            pass

    # Weight surcharge: >30kg adds 5% per 10kg
    try:
        weight_val = Decimal(str(weight or 0))
        if weight_val > 30:
            over = weight_val - Decimal('30')
            steps = int((over / Decimal('10')).to_integral_value(rounding='ROUND_CEILING'))
            surcharge = (base_fee * Decimal('0.05') * Decimal(steps))
            base_fee += surcharge
    except Exception:
        pass

    return base_fee.quantize(Decimal('0.01'))


def optimize_route(deliveries, start_location=None):
    """
    Simple route optimization (TSP approximation)
    In production, integrate with Google Maps API or similar
    """
    if not deliveries:
        return []
    
    # Simple distance-based sorting
    sorted_deliveries = sorted(
        deliveries,
        key=lambda d: (
            d.recipient_latitude or 0,
            d.recipient_longitude or 0
        )
    )
    
    return sorted_deliveries


def send_delivery_notification(delivery, notification_type, recipient=None, context=None):
    """
    Send delivery notifications via email or other channels
    """
    if context is None:
        context = {}
    
    # Build a safe tracking URL; tests may not provide SITE_URL so fall back to a relative path
    site_url = getattr(settings, 'SITE_URL', '') or getattr(settings, 'DEFAULT_SITE_URL', '')
    site_url = site_url.rstrip('/') if site_url else ''
    tracking_path = f"/delivery/track/{delivery.tracking_number}/"
    tracking_url = f"{site_url}{tracking_path}" if site_url else tracking_path

    context.update({
        'delivery': delivery,
        'tracking_url': tracking_url,
        'notification_type': notification_type,
    })
    
    # Email notification
    if recipient and hasattr(recipient, 'email') and recipient.email:
        try:
            subject = f"Delivery Update: {delivery.tracking_number}"
            html_message = render_to_string('delivery/email/notification.html', context)
            plain_message = render_to_string('delivery/email/notification.txt', context)

            try:
                from baysoko.utils.email_helpers import render_and_send
                recipients = [e for e in [getattr(recipient, 'email', None)] if e]
                if recipients:
                    render_and_send('delivery/email/notification.html', 'delivery/email/notification.txt', context, subject, recipients)
            except Exception:
                try:
                    from django.core.mail import send_mail
                    send_mail(subject=subject, message=plain_message, html_message=html_message, from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[recipient.email], fail_silently=True)
                except Exception:
                    logger.exception('Failed to send delivery notification email via fallback')
            
            # Create notification record
            from .models import DeliveryNotification
            DeliveryNotification.objects.create(
                user=recipient,
                delivery_request=delivery,
                notification_type=notification_type,
                title=f"Delivery {notification_type.replace('_', ' ').title()}",
                message=f"Delivery {delivery.tracking_number} has been {notification_type.replace('_', ' ')}",
                data=context
            )
            
        except Exception as e:
            logger.error(f"Failed to send delivery notification: {str(e)}")
    
    return True


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two coordinates using Haversine formula
    """
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371  # Earth's radius in kilometers
    
    lat1 = radians(float(lat1))
    lon1 = radians(float(lon1))
    lat2 = radians(float(lat2))
    lon2 = radians(float(lon2))
    
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    distance = R * c
    return round(distance, 2)


def validate_coordinates(latitude, longitude):
    """
    Validate latitude and longitude values
    """
    try:
        lat = float(latitude)
        lng = float(longitude)
        
        if not (-90 <= lat <= 90):
            return False, "Latitude must be between -90 and 90"
        if not (-180 <= lng <= 180):
            return False, "Longitude must be between -180 and 180"
        
        return True, (lat, lng)
    except (ValueError, TypeError):
        return False, "Invalid coordinate format"


def generate_tracking_number():
    """
    Generate unique tracking number
    """
    import uuid
    import datetime
    timestamp = datetime.datetime.now().strftime('%y%m%d')
    unique_id = str(uuid.uuid4())[:8].upper()
    return f"DL{timestamp}{unique_id}"

def get_deliveries_for_user(user, store_id=None):
    """
    Get deliveries filtered by user's permissions
    """
    from .models import DeliveryRequest
    from storefront.models import Store
    
    # Admin/superusers see all
    if user.is_staff or user.is_superuser:
        queryset = DeliveryRequest.objects.all()
        if store_id:
            queryset = queryset.filter(
                Q(metadata__store_id=store_id) | 
                Q(metadata__store=str(store_id))
            )
        return queryset
    
    # Delivery persons see their own assignments
    if hasattr(user, 'delivery_person'):
        return DeliveryRequest.objects.filter(delivery_person=user.delivery_person)
    
    # Sellers see deliveries for their stores
    stores = Store.objects.filter(owner=user)
    if stores.exists():
        if store_id and store_id.isdigit():
            store_id_int = int(store_id)
            # Verify the store belongs to the user
            if stores.filter(id=store_id_int).exists():
                return DeliveryRequest.objects.filter(
                    Q(metadata__store_id=store_id_int) | 
                    Q(metadata__store=str(store_id_int))
                )
        
        # Get all store IDs for the user
        store_ids = [store.id for store in stores]
        
        # Create a complex query for all stores
        store_lookup = []
        for store_id_val in store_ids:
            store_lookup.append(Q(metadata__store_id=store_id_val))
            store_lookup.append(Q(metadata__store=str(store_id_val)))
        
        if store_lookup:
            from functools import reduce
            from operator import or_
            combined_query = reduce(or_, store_lookup)
            return DeliveryRequest.objects.filter(combined_query)
    
    # Regular users without a store should not access the delivery system.
    # Only return deliveries for users who own stores (sellers) or delivery personnel.
    stores = Store.objects.filter(owner=user)
    if stores.exists():
        store_ids = [s.id for s in stores]
        store_lookup = []
        for store_id_val in store_ids:
            store_lookup.append(Q(metadata__store_id=store_id_val))
            store_lookup.append(Q(metadata__store=str(store_id_val)))
        if store_lookup:
            from functools import reduce
            from operator import or_
            combined_query = reduce(or_, store_lookup)
            return DeliveryRequest.objects.filter(combined_query)

    # Delivery personnel may view their assignments
    if hasattr(user, 'delivery_person'):
        return DeliveryRequest.objects.filter(delivery_person=user.delivery_person)

    # No access for ordinary users without stores
    return DeliveryRequest.objects.none()
