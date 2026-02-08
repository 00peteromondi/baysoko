"""
API views for delivery management
"""
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Count, Sum, Avg, F, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import json

from ..models import (
    DeliveryRequest, DeliveryPerson, DeliveryService, DeliveryZone,
    DeliveryStatusHistory, DeliveryRating
)
from ..serializers import (
    DeliveryRequestSerializer, DeliveryPersonSerializer,
    DeliveryServiceSerializer, DeliveryZoneSerializer,
    DeliveryStatusHistorySerializer, DeliveryRatingSerializer
)
from ..permissions import IsDeliveryPerson, IsDeliveryOwner
from ..utils import calculate_delivery_fee
from django.conf import settings
from rest_framework.permissions import AllowAny


class DeliveryViewSet(viewsets.ModelViewSet):
    """API endpoint for delivery requests"""
    queryset = DeliveryRequest.objects.all()
    serializer_class = DeliveryRequestSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = DeliveryRequest.objects.all()
        
        # Filter by status if provided
        status = self.request.query_params.get('status', None)
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        # Filter by delivery person if provided
        delivery_person_id = self.request.query_params.get('delivery_person_id', None)
        if delivery_person_id:
            queryset = queryset.filter(delivery_person_id=delivery_person_id)
        
        # For non-admin users, only allow access to store owners (sellers) or delivery persons
        user = self.request.user
        if not (user.is_staff or user.is_superuser):
            # Delivery person may see their own assignments
            if hasattr(user, 'delivery_person'):
                queryset = queryset.filter(delivery_person=user.delivery_person)
            else:
                # Sellers (store owners) can see deliveries for their stores only
                from storefront.models import Store
                stores = Store.objects.filter(owner=user)
                if stores.exists():
                    store_ids = [s.id for s in stores]
                    store_lookup = list(store_ids) + [str(s) for s in store_ids]
                    queryset = queryset.filter(
                        Q(metadata__store_id__in=store_lookup) |
                        Q(metadata__store__in=store_lookup)
                    )
                else:
                    # No access for regular users without stores
                    return DeliveryRequest.objects.none()
        
        return queryset.order_by('-created_at')
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def update_status(self, request, pk=None):
        """Update delivery status"""
        delivery = self.get_object()
        new_status = request.data.get('status')
        notes = request.data.get('notes', '')
        
        if not new_status:
            return Response(
                {'error': 'Status is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check permissions: allow admin, delivery person assigned, or store owner of the delivery
        user = request.user
        if not (user.is_staff or user.is_superuser):
            if hasattr(user, 'delivery_person'):
                if delivery.delivery_person != user.delivery_person:
                    return Response(
                        {'error': 'You can only update your own deliveries'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            else:
                # Check store ownership via metadata
                try:
                    from storefront.models import Store
                    stores = Store.objects.filter(owner=user)
                    if stores.exists():
                        store_id = None
                        if isinstance(delivery.metadata, dict):
                            store_id = delivery.metadata.get('store_id')
                        if store_id:
                            try:
                                if stores.filter(id=int(store_id)).exists():
                                    pass
                                else:
                                    return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
                            except Exception:
                                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
                        else:
                            return Response({'error': 'You do not have permission to update delivery status'}, status=status.HTTP_403_FORBIDDEN)
                    else:
                        return Response({'error': 'You do not have permission to update delivery status'}, status=status.HTTP_403_FORBIDDEN)
                except Exception:
                    return Response({'error': 'You do not have permission to update delivery status'}, status=status.HTTP_403_FORBIDDEN)
        
        # Validate status transition
        valid_transitions = {
            'pending': ['accepted', 'cancelled'],
            'accepted': ['assigned', 'cancelled'],
            'assigned': ['picked_up', 'cancelled'],
            'picked_up': ['in_transit', 'cancelled'],
            'in_transit': ['out_for_delivery', 'delivered', 'failed'],
            'out_for_delivery': ['delivered', 'failed'],
            'delivered': [],
            'failed': ['returned', 'accepted'],
            'cancelled': [],
            'returned': ['accepted', 'cancelled'],
        }
        
        current_status = delivery.status
        if new_status not in valid_transitions.get(current_status, []):
            return Response(
                {'error': f'Invalid status transition from {current_status} to {new_status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update status
        delivery.update_status(new_status, notes)
        
        return Response({
            'success': True,
            'message': f'Status updated to {new_status}',
            'delivery': DeliveryRequestSerializer(delivery).data
        })


class DriverViewSet(viewsets.ModelViewSet):
    """API endpoint for delivery personnel"""
    queryset = DeliveryPerson.objects.all()
    serializer_class = DeliveryPersonSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    @action(detail=True, methods=['post'], permission_classes=[IsDeliveryPerson])
    def update_location(self, request, pk=None):
        """Update driver location"""
        driver = self.get_object()
        
        # Ensure only the driver can update their own location
        if request.user.delivery_person != driver:
            return Response(
                {'error': 'You can only update your own location'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        lat = request.data.get('latitude')
        lng = request.data.get('longitude')
        
        if not lat or not lng:
            return Response(
                {'error': 'Latitude and longitude are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            driver.update_location(float(lat), float(lng))
            return Response({
                'success': True,
                'message': 'Location updated successfully',
                'location': {'latitude': lat, 'longitude': lng}
            })
        except ValueError:
            return Response(
                {'error': 'Invalid coordinates'},
                status=status.HTTP_400_BAD_REQUEST
            )


class ServiceViewSet(viewsets.ModelViewSet):
    """API endpoint for delivery services"""
    queryset = DeliveryService.objects.filter(is_active=True)
    serializer_class = DeliveryServiceSerializer
    permission_classes = [IsAuthenticated]


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_delivery_fee_api(request):
    """Calculate delivery fee based on parameters"""
    try:
        weight = Decimal(request.data.get('weight', '0'))
        service_id = request.data.get('service_id')
        zone_id = request.data.get('zone_id')
        distance = request.data.get('distance')
        
        service = None
        zone = None
        
        if service_id:
            service = get_object_or_404(DeliveryService, id=service_id)
        if zone_id:
            zone = get_object_or_404(DeliveryZone, id=zone_id)
        
        fee = calculate_delivery_fee(
            weight=weight,
            service_type=service,
            zone=zone,
            distance=distance
        )
        
        return Response({
            'delivery_fee': str(fee),
            'currency': 'KES',
            'calculation': {
                'weight': str(weight),
                'service': service.name if service else 'Standard',
                'zone': zone.name if zone else 'Default',
                'distance': distance
            }
        })
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def track_delivery_api(request, tracking_number):
    """API endpoint for tracking deliveries"""
    delivery = get_object_or_404(DeliveryRequest, tracking_number=tracking_number)
    
    # For public tracking, return limited info
    serializer = DeliveryRequestSerializer(delivery)
    
    # Add status history
    status_history = DeliveryStatusHistory.objects.filter(
        delivery_request=delivery
    ).order_by('-created_at')
    status_serializer = DeliveryStatusHistorySerializer(status_history, many=True)
    
    return Response({
        'tracking_number': delivery.tracking_number,
        'status': delivery.get_status_display(),
        'status_code': delivery.status,
        'recipient_name': delivery.recipient_name,
        'estimated_delivery_time': delivery.estimated_delivery_time,
        'actual_delivery_time': delivery.actual_delivery_time,
        'status_history': status_serializer.data,
        'last_update': delivery.updated_at,
    })


# Analytics API Views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def delivery_analytics_api(request):
    """Get delivery analytics data"""
    user = request.user
    
    # Time period
    period = request.GET.get('period', 'week')
    
    if period == 'week':
        start_date = timezone.now() - timedelta(days=7)
    elif period == 'month':
        start_date = timezone.now() - timedelta(days=30)
    elif period == 'quarter':
        start_date = timezone.now() - timedelta(days=90)
    else:
        start_date = timezone.now() - timedelta(days=7)
    
    # Base queryset
    queryset = DeliveryRequest.objects.filter(created_at__gte=start_date)
    
    # Filter by user's stores if not admin
    if not (user.is_staff or user.is_superuser):
        from storefront.models import Store
        stores = Store.objects.filter(owner=user)
        if stores.exists():
            store_ids = [s.id for s in stores]
            store_lookup = list(store_ids) + [str(s) for s in store_ids]
            queryset = queryset.filter(
                Q(metadata__store_id__in=store_lookup) | 
                Q(metadata__store__in=store_lookup)
            )
        elif hasattr(user, 'delivery_person'):
            # For delivery persons, show their own deliveries
            queryset = queryset.filter(delivery_person=user.delivery_person)
        else:
            # Regular users - show deliveries associated with their orders
            queryset = queryset.filter(
                Q(metadata__user_id=user.id) |
                Q(recipient_email=user.email)
            )
    
    # Calculate metrics
    total_deliveries = queryset.count()
    completed = queryset.filter(status='delivered').count()
    success_rate = (completed / total_deliveries * 100) if total_deliveries > 0 else 0
    
    # Average delivery time
    completed_deliveries = queryset.filter(
        status='delivered',
        actual_delivery_time__isnull=False,
        pickup_time__isnull=False
    )
    
    avg_delivery_hours = None
    if completed_deliveries.exists():
        # Calculate average delivery time in hours
        total_hours = 0
        count = 0
        for delivery in completed_deliveries:
            if delivery.actual_delivery_time and delivery.pickup_time:
                duration = delivery.actual_delivery_time - delivery.pickup_time
                total_hours += duration.total_seconds() / 3600
                count += 1
        
        if count > 0:
            avg_delivery_hours = total_hours / count
    
    # Revenue
    revenue = queryset.filter(
        payment_status='paid'
    ).aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    # Status distribution
    status_distribution = queryset.values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    # Weekly activity
    weekly_data = []
    for i in range(7):
        date = (timezone.now() - timedelta(days=i)).date()
        count = queryset.filter(created_at__date=date).count()
        weekly_data.append({
            'date': date.isoformat(),
            'day': date.strftime('%a'),
            'count': count
        })
    
    return Response({
        'period': period,
        'start_date': start_date.date().isoformat(),
        'end_date': timezone.now().date().isoformat(),
        'metrics': {
            'total_deliveries': total_deliveries,
            'completed_deliveries': completed,
            'success_rate': round(success_rate, 2),
            'average_delivery_hours': round(avg_delivery_hours, 2) if avg_delivery_hours else None,
            'revenue': float(revenue),
            'currency': 'KES',
        },
        'status_distribution': list(status_distribution),
        'weekly_activity': weekly_data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def status_distribution_api(request):
    """Get delivery status distribution"""
    user = request.user
    
    queryset = DeliveryRequest.objects.all()
    
    # Filter by user's stores if not admin
    if not (user.is_staff or user.is_superuser):
        from storefront.models import Store
        stores = Store.objects.filter(owner=user)
        if stores.exists():
            store_ids = [s.id for s in stores]
            store_lookup = list(store_ids) + [str(s) for s in store_ids]
            queryset = queryset.filter(
                Q(metadata__store_id__in=store_lookup) | 
                Q(metadata__store__in=store_lookup)
            )
        elif hasattr(user, 'delivery_person'):
            queryset = queryset.filter(delivery_person=user.delivery_person)
        else:
            queryset = queryset.filter(
                Q(metadata__user_id=user.id) |
                Q(recipient_email=user.email)
            )
    
    # Date filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    
    distribution = queryset.values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    return Response(list(distribution))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def weekly_activity_api(request):
    """Get weekly delivery activity"""
    user = request.user
    
    queryset = DeliveryRequest.objects.all()
    
    # Filter by user's stores if not admin
    if not (user.is_staff or user.is_superuser):
        from storefront.models import Store
        stores = Store.objects.filter(owner=user)
        if stores.exists():
            store_ids = [s.id for s in stores]
            store_lookup = list(store_ids) + [str(s) for s in store_ids]
            queryset = queryset.filter(
                Q(metadata__store_id__in=store_lookup) | 
                Q(metadata__store__in=store_lookup)
            )
        elif hasattr(user, 'delivery_person'):
            queryset = queryset.filter(delivery_person=user.delivery_person)
        else:
            queryset = queryset.filter(
                Q(metadata__user_id=user.id) |
                Q(recipient_email=user.email)
            )
    
    # Get activity for last 7 days
    weekly_data = []
    for i in range(6, -1, -1):  # Last 7 days including today
        date = (timezone.now() - timedelta(days=i)).date()
        count = queryset.filter(created_at__date=date).count()
        weekly_data.append({
            'date': date.isoformat(),
            'day': date.strftime('%A'),
            'short_day': date.strftime('%a'),
            'count': count
        })
    
    return Response(weekly_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def driver_performance_api(request):
    """Get driver performance analytics"""
    drivers = DeliveryPerson.objects.all()
    
    performance_data = []
    for driver in drivers:
        assignments = driver.assignments.all()
        completed = assignments.filter(status='delivered')
        
        # Calculate metrics
        total = assignments.count()
        completed_count = completed.count()
        completion_rate = (completed_count / total * 100) if total > 0 else 0
        
        # Average rating
        avg_rating = completed.aggregate(
            avg_rating=Avg('rating__rating')
        )['avg_rating'] or 0
        
        # Average delivery time
        avg_delivery_hours = None
        if completed.exists():
            total_hours = 0
            valid_count = 0
            for delivery in completed:
                if delivery.actual_delivery_time and delivery.pickup_time:
                    duration = delivery.actual_delivery_time - delivery.pickup_time
                    total_hours += duration.total_seconds() / 3600
                    valid_count += 1
            
            if valid_count > 0:
                avg_delivery_hours = total_hours / valid_count
        
        performance_data.append({
            'driver_id': driver.id,
            'driver_name': driver.user.get_full_name() or driver.user.username,
            'employee_id': driver.employee_id,
            'vehicle_type': driver.vehicle_type,
            'total_assignments': total,
            'completed_assignments': completed_count,
            'completion_rate': round(completion_rate, 2),
            'average_rating': round(float(avg_rating), 2),
            'average_delivery_hours': round(avg_delivery_hours, 2) if avg_delivery_hours else None,
            'current_status': driver.current_status,
            'is_available': driver.is_available,
        })
    
    return Response(performance_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def zone_performance_api(request):
    """Get delivery zone performance analytics"""
    zones = DeliveryZone.objects.filter(is_active=True)
    
    zone_data = []
    for zone in zones:
        deliveries = DeliveryRequest.objects.filter(delivery_zone=zone)
        
        # Calculate metrics
        total = deliveries.count()
        completed = deliveries.filter(status='delivered').count()
        completion_rate = (completed / total * 100) if total > 0 else 0
        
        # Average delivery fee
        avg_fee = deliveries.aggregate(
            avg_fee=Avg('delivery_fee')
        )['avg_fee'] or 0
        
        # Revenue
        revenue = deliveries.filter(
            payment_status='paid'
        ).aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        zone_data.append({
            'zone_id': zone.id,
            'zone_name': zone.name,
            'delivery_fee': float(zone.delivery_fee),
            'total_deliveries': total,
            'completed_deliveries': completed,
            'completion_rate': round(completion_rate, 2),
            'average_delivery_fee': round(float(avg_fee), 2),
            'revenue': float(revenue),
            'currency': 'KES',
        })
    
    return Response(zone_data)


@api_view(['POST'])
@permission_classes([AllowAny])
def webhook_receiver(request):
    """Receive webhook posts from external delivery systems.

    Authentication: accept either X-API-Key == DELIVERY_WEBHOOK_KEY or
    Authorization: Bearer <DELIVERY_SYSTEM_API_KEY>.
    """
    # Accept API key from header
    x_api_key = request.headers.get('X-API-Key') or request.META.get('HTTP_X_API_KEY')
    auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION')

    key_ok = False
    if x_api_key and x_api_key == getattr(settings, 'DELIVERY_WEBHOOK_KEY', None):
        key_ok = True
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ', 1)[1]
        if token == getattr(settings, 'DELIVERY_SYSTEM_API_KEY', None):
            key_ok = True

    if not key_ok:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

    data = request.data
    tracking = data.get('tracking_number') or data.get('tracking')
    status_val = data.get('status')

    if not tracking or not status_val:
        return Response({'error': 'tracking_number and status are required'}, status=status.HTTP_400_BAD_REQUEST)

    delivery = DeliveryRequest.objects.filter(tracking_number=tracking).first()
    if not delivery:
        return Response({'error': 'Delivery not found'}, status=status.HTTP_404_NOT_FOUND)

    # Update delivery status
    delivery.status = status_val
    # If delivered, set actual_delivery_time if not set
    if status_val == 'delivered' and not delivery.actual_delivery_time:
        delivery.actual_delivery_time = timezone.now()
    delivery.save()

    # Try to update linked order via integration mapping (best-effort)
    try:
        from ..integration import update_order_from_delivery
        update_order_from_delivery(delivery)
    except Exception:
        pass

    return Response({'status': 'ok'})

