from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count, Sum, Avg, F
from django.utils import timezone
from datetime import datetime, timedelta
import json
import csv
from decimal import Decimal
import logging
from django.db.models import Count, Sum, Avg, F, DurationField
from django.db.models.functions import TruncDate
from django.utils.timezone import make_aware
from django.contrib import messages


logger = logging.getLogger(__name__)


from .models import (
    DeliveryRequest, DeliveryPerson, DeliveryService, DeliveryZone,
    DeliveryStatusHistory, DeliveryProof, DeliveryRoute, DeliveryRating,
    DeliveryNotification, DeliveryPackageType, DeliveryTimeSlot,
    DeliveryPricingRule, DeliveryAnalytics
)
from .forms import (
    DeliveryRequestForm, DeliveryPersonForm, DeliveryServiceForm,
    DeliveryZoneForm, DeliveryProofForm, DeliveryRouteForm,
    DeliveryRatingForm, DeliveryTimeSlotForm, DeliveryPricingRuleForm
)
from .utils import calculate_delivery_fee, optimize_route, send_delivery_notification
from .decorators import delivery_person_required, admin_required, seller_or_delivery_or_admin_required
from storefront.models import Store


def _get_deliveries_for_user(user, request=None):
    """Module-level helper to return deliveries scoped to the given user.

    If `request` is provided, will respect a `store`/`store_id` GET filter
    but only if the store belongs to the user.
    """
    # Admin/superusers see all
    if user.is_staff or user.is_superuser:
        return DeliveryRequest.objects.all()

    # Delivery persons see their own assignments
    if hasattr(user, 'delivery_person'):
        return DeliveryRequest.objects.filter(delivery_person=user.delivery_person)

    # Sellers see deliveries for their stores only (require store ownership)
    try:
        stores = Store.objects.filter(owner=user)
        if not stores.exists():
            return DeliveryRequest.objects.none()
        store_ids = [s.id for s in stores]

        # Build store lookup Q
        store_lookup = []
        for store_id in store_ids:
            store_lookup.append(Q(metadata__store_id=store_id))
            store_lookup.append(Q(metadata__store=str(store_id)))
        from functools import reduce
        from operator import or_
        store_q = reduce(or_, store_lookup) if store_lookup else None

        # Deliveries tied to orders that contain listings sold by this user
        try:
            from listings.models import Order
            sold_order_ids = Order.objects.filter(
                order_items__listing__seller=user
            ).values_list('id', flat=True).distinct()
            sold_order_ids = [str(i) for i in sold_order_ids]
        except Exception:
            sold_order_ids = []

        seller_q = Q()
        if sold_order_ids:
            seller_q = Q(order_id__in=sold_order_ids) | Q(metadata__seller_id=user.id) | Q(metadata__seller=str(user.id))

        # Respect explicit store filter if provided and belongs to the user
        if request is not None:
            store_filter = request.GET.get('store') or request.GET.get('store_id') or request.GET.get('storeId')
            if store_filter and str(store_filter).isdigit():
                sf = int(store_filter)
                if sf in store_ids:
                    return DeliveryRequest.objects.filter(
                        Q(metadata__store_id=sf) | Q(metadata__store=str(sf))
                    )
                else:
                    return DeliveryRequest.objects.none()

        # Combine
        if store_q and seller_q:
            combined_q = store_q | seller_q
            return DeliveryRequest.objects.filter(combined_q)
        if store_q:
            return DeliveryRequest.objects.filter(store_q)
        if seller_q:
            return DeliveryRequest.objects.filter(seller_q)
    except Exception:
        return DeliveryRequest.objects.none()

    return DeliveryRequest.objects.none()


class DashboardView(LoginRequiredMixin, TemplateView):
    """Delivery system dashboard"""
    template_name = 'delivery/dashboard.html'
    def dispatch(self, request, *args, **kwargs):
        user = request.user
        # Allow admins and delivery persons
        if user.is_staff or user.is_superuser or hasattr(user, 'delivery_person'):
            return super().dispatch(request, *args, **kwargs)

        # Allow only users who own at least one store
        try:
            from storefront.models import Store
            if not Store.objects.filter(owner=user).exists():
                from django.contrib import messages
                from django.shortcuts import redirect
                messages.warning(request, 'Delivery system is for sellers and delivery personnel only.')
                return redirect('order_list')
        except Exception:
            from django.contrib import messages
            from django.shortcuts import redirect
            messages.warning(request, 'Delivery system is for sellers and delivery personnel only.')
            return redirect('order_list')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get statistics based on user type
        today = timezone.now().date()
        start_of_month = today.replace(day=1)

        # Determine base queryset based on user role
        base_qs = _get_deliveries_for_user(user, request=self.request)

        # Store the base queryset for use in other calculations
        context['base_deliveries'] = base_qs

        context['total_deliveries'] = base_qs.count()
        context['pending_deliveries'] = base_qs.filter(
            status__in=['pending', 'accepted', 'assigned']
        ).count()
        context['in_transit_deliveries'] = base_qs.filter(
            status__in=['picked_up', 'in_transit', 'out_for_delivery']
        ).count()
        context['completed_deliveries'] = base_qs.filter(
            status='delivered'
        ).count()
        context['today_deliveries'] = base_qs.filter(
            created_at__date=today
        ).count()

        # Revenue statistics (only for relevant deliveries)
        context['monthly_revenue'] = base_qs.filter(
            created_at__gte=start_of_month,
            payment_status='paid'
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        # Recent deliveries with store filter
        status_filter = self.request.GET.get('status')
        store_filter = self.request.GET.get('store_id')

        recent_qs = base_qs.select_related(
            'delivery_person', 'delivery_service'
        ).order_by('-created_at')[:10]

        # Apply status filter if provided
        if status_filter:
            recent_qs = base_qs.filter(status=status_filter).select_related(
                'delivery_person', 'delivery_service'
            ).order_by('-created_at')[:10]

        context['recent_deliveries'] = recent_qs
        context['filter_status'] = status_filter or ''
        context['status_choices'] = DeliveryRequest.STATUS_CHOICES

        # Get user's stores for filter dropdown
        try:
            from storefront.models import Store
            stores = Store.objects.filter(owner=user)
            context['stores'] = stores
            context['selected_store_id'] = store_filter if store_filter else None
        except Exception:
            context['stores'] = []
            context['selected_store_id'] = None

        # Delivery person statistics
        if hasattr(user, 'delivery_person'):
            context['is_delivery_person'] = True
            delivery_person = user.delivery_person
            context['my_assignments'] = DeliveryRequest.objects.filter(
                delivery_person=delivery_person,
                status__in=['assigned', 'picked_up', 'in_transit', 'out_for_delivery']
            ).order_by('-priority', 'estimated_delivery_time')[:5]
            context['my_stats'] = {
                'total': delivery_person.total_deliveries,
                'completed': delivery_person.completed_deliveries,
                'rating': delivery_person.rating,
            }

        # Notifications
        context['unread_notifications'] = DeliveryNotification.objects.filter(
            user=self.request.user,
            is_read=False
        ).order_by('-created_at')[:5]

        # Chart data
        context['status_distribution'] = self.get_status_distribution(base_qs)
        context['weekly_activity'] = self.get_weekly_activity(base_qs)

        # Add user role context for templates
        context['is_admin'] = user.is_staff or user.is_superuser
        context['is_seller'] = getattr(context.get('stores'), 'exists', lambda: False)() or (context['stores'] and len(context['stores']) > 0)

        return context
    
    def get_filtered_deliveries(self, user):
        # Delegate to module helper which supports request-based filtering
        return _get_deliveries_for_user(user, request=self.request)
    
    def get_status_distribution(self, base_qs):
        """Get delivery status distribution for chart"""
        data = base_qs.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        return list(data)
    
    def get_weekly_activity(self, base_qs):
        """Get weekly delivery activity"""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        activity = []
        for i in range(7):
            date = week_ago + timedelta(days=i)
            count = base_qs.filter(created_at__date=date).count()
            activity.append({
                'date': date.strftime('%Y-%m-%d'),
                'day': date.strftime('%a'),
                'count': count
            })
        
        return activity

class DeliveryListView(LoginRequiredMixin, ListView):
    """List all deliveries"""
    model = DeliveryRequest
    template_name = 'delivery/delivery_list.html'
    context_object_name = 'deliveries'
    paginate_by = 20
    
    def get_queryset(self):
        user = self.request.user
        
        # Start with appropriate base queryset
        if user.is_staff or user.is_superuser:
            queryset = DeliveryRequest.objects.all()
        elif hasattr(user, 'delivery_person'):
            queryset = DeliveryRequest.objects.filter(delivery_person=user.delivery_person)
        else:
            # For sellers and regular users: sellers should only see deliveries
            # that belong to their stores or deliveries tied to orders that
            # include listings sold by them.
            try:
                from storefront.models import Store
                stores = Store.objects.filter(owner=user)
                # Require store ownership for seller access
                if not stores.exists():
                    return DeliveryRequest.objects.none()
                store_ids = [s.id for s in stores]

                store_q = None
                if store_ids:
                    store_lookup = []
                    for store_id in store_ids:
                        store_lookup.append(Q(metadata__store_id=store_id))
                        store_lookup.append(Q(metadata__store=str(store_id)))
                    from functools import reduce
                    from operator import or_
                    store_q = reduce(or_, store_lookup)

                # Deliveries tied to orders that contain listings sold by this user
                try:
                    from listings.models import Order
                    sold_order_ids = Order.objects.filter(
                        order_items__listing__seller=user
                    ).values_list('id', flat=True).distinct()
                    sold_order_ids = [str(i) for i in sold_order_ids]
                except Exception:
                    sold_order_ids = []

                seller_q = Q()
                if sold_order_ids:
                    seller_q = Q(order_id__in=sold_order_ids) | Q(metadata__seller_id=user.id) | Q(metadata__seller=str(user.id))

                if store_q and seller_q:
                    queryset = DeliveryRequest.objects.filter(store_q | seller_q)
                elif store_q:
                    queryset = DeliveryRequest.objects.filter(store_q)
                elif seller_q:
                    queryset = DeliveryRequest.objects.filter(seller_q)
                else:
                    # Regular users without stores should not access delivery listings here
                    queryset = DeliveryRequest.objects.none()
            except Exception:
                queryset = DeliveryRequest.objects.none()
        
        # Apply additional filters
        queryset = queryset.select_related(
            'delivery_person', 'delivery_service', 'delivery_zone'
        ).order_by('-created_at')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by delivery person
        if self.request.GET.get('my_deliveries') and hasattr(self.request.user, 'delivery_person'):
            queryset = queryset.filter(delivery_person=self.request.user.delivery_person)
        
        # Filter by date range
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(tracking_number__icontains=search) |
                Q(order_id__icontains=search) |
                Q(recipient_name__icontains=search) |
                Q(recipient_phone__icontains=search) |
                Q(pickup_name__icontains=search)
            )
        
        # Filter by store if seller has multiple stores
        if not (user.is_staff or user.is_superuser) and not hasattr(user, 'delivery_person'):
            store_filter = self.request.GET.get('store')
            if store_filter and store_filter.isdigit():
                store_id = int(store_filter)
                # Ensure the requested store belongs to the requesting user
                try:
                    from storefront.models import Store
                    if not Store.objects.filter(id=store_id, owner=user).exists():
                        # Deny access to other sellers' stores
                        return DeliveryRequest.objects.none()
                except Exception:
                    return DeliveryRequest.objects.none()

                queryset = queryset.filter(
                    Q(metadata__store_id=store_id) | 
                    Q(metadata__store=str(store_id))
                )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = DeliveryRequest.STATUS_CHOICES
        context['filter_status'] = self.request.GET.get('status', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        context['search'] = self.request.GET.get('search', '')
        context['my_deliveries'] = self.request.GET.get('my_deliveries', '')
        
        # Add store filter for sellers
        user = self.request.user
        if not (user.is_staff or user.is_superuser) and not hasattr(user, 'delivery_person'):
            try:
                from storefront.models import Store
                stores = Store.objects.filter(owner=user)
                context['stores'] = stores
                context['store_filter'] = self.request.GET.get('store', '')
            except Exception:
                context['stores'] = []
                context['store_filter'] = ''
        
        return context    


    # (dispatch decorators applied after class definitions)


class DeliveryDetailView(LoginRequiredMixin, DetailView):
    """View delivery details"""
    model = DeliveryRequest
    template_name = 'delivery/delivery_detail.html'
    context_object_name = 'delivery'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get status history with safe user info
        status_history = []
        for history in self.object.status_history.all().order_by('-created_at'):
            status_history.append({
                'id': history.id,
                'old_status': history.old_status,
                'old_status_display': history.get_old_status_display(),
                'new_status': history.new_status,
                'new_status_display': history.get_new_status_display(),
                'notes': history.notes,
                'created_at': history.created_at,
                'changed_by': history.changed_by,
                'changed_by_display': history.get_changed_by_display(),  # Use the safe method
            })
        
        context['status_history'] = status_history
        context['proofs'] = self.object.proofs.all()
        context['can_update_status'] = self.can_update_status()
        context['status_choices'] = DeliveryRequest.STATUS_CHOICES
        
        # Add user's stores context for permission checking
        user = self.request.user
        if not (user.is_staff or user.is_superuser) and not hasattr(user, 'delivery_person'):
            try:
                from storefront.models import Store
                stores = Store.objects.filter(owner=user)
                context['user_stores'] = stores
            except Exception:
                context['user_stores'] = []
        
        return context

    def dispatch(self, request, *args, **kwargs):
        # Ensure only allowed users can view this delivery
        user = request.user
        if not user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        # Admins and delivery persons allowed
        if user.is_staff or user.is_superuser or hasattr(user, 'delivery_person'):
            return super().dispatch(request, *args, **kwargs)

        # Otherwise, check store ownership or sold items
        try:
            delivery = self.get_object()
            # If delivery has store metadata, only that store owner can view
            if isinstance(delivery.metadata, dict):
                store_id = delivery.metadata.get('store_id')
                if store_id:
                    try:
                        from storefront.models import Store
                        if Store.objects.filter(id=int(store_id), owner=user).exists():
                            return super().dispatch(request, *args, **kwargs)
                    except Exception:
                        pass

            # Allow sellers who have items in the linked order
            if delivery.order_id:
                try:
                    from listings.models import Order
                    oid = None
                    try:
                        oid = int(delivery.order_id)
                    except Exception:
                        parts = str(delivery.order_id).split('_')
                        try:
                            oid = int(parts[-1])
                        except Exception:
                            oid = None
                    if oid:
                        order = Order.objects.filter(id=oid).first()
                        if order and order.order_items.filter(listing__seller=user).exists():
                            return super().dispatch(request, *args, **kwargs)
                except Exception:
                    pass
        except Exception:
            pass

        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('You do not have permission to view this delivery.')
    
    def can_update_status(self):
        """Check if user can update delivery status"""
        user = self.request.user
        delivery = self.get_object()
        
        if user.is_superuser or user.is_staff:
            return True
        
        if hasattr(user, 'delivery_person'):
            return delivery.delivery_person == user.delivery_person
        
        # Check if user owns the store that this delivery belongs to
        try:
            from storefront.models import Store
            stores = Store.objects.filter(owner=user)
            # If the delivery has store_id metadata and the user owns that store
            if stores.exists() and isinstance(delivery.metadata, dict):
                store_id = delivery.metadata.get('store_id')
                if store_id:
                    try:
                        store_id_int = int(store_id)
                        if stores.filter(id=store_id_int).exists():
                            return True
                    except ValueError:
                        if stores.filter(id=str(store_id)).exists():
                            return True

            # Additionally allow sellers who sold items in the linked order to update
            try:
                if delivery.order_id:
                    from listings.models import Order
                    # Match numeric order ids
                    try:
                        oid = int(delivery.order_id)
                    except Exception:
                        # Try to extract trailing number if integration uses prefixes
                        parts = str(delivery.order_id).split('_')
                        oid = None
                        try:
                            oid = int(parts[-1])
                        except Exception:
                            oid = None

                    if oid:
                        order = Order.objects.filter(id=oid).first()
                        if order and order.order_items.filter(listing__seller=user).exists():
                            return True
            except Exception:
                pass
        except Exception:
            pass
        
        return False

class CreateDeliveryView(LoginRequiredMixin, CreateView):
    """Create a new delivery request"""
    model = DeliveryRequest
    form_class = DeliveryRequestForm
    template_name = 'delivery/create_delivery.html'
    success_url = reverse_lazy('delivery:dashboard')
    
    def form_valid(self, form):
        # Set tracking number
        form.instance.tracking_number = f"DLV{timezone.now().strftime('%Y%m%d%H%M%S')}"
        
        # Calculate delivery fee
        delivery_fee = calculate_delivery_fee(
            weight=form.cleaned_data['package_weight'],
            distance=None,  # Will be calculated from coordinates
            service_type=form.cleaned_data.get('delivery_service'),
            zone=form.cleaned_data.get('delivery_zone')
        )
        form.instance.delivery_fee = delivery_fee
        form.instance.total_amount = delivery_fee
        
        # Set created by
        form.instance.metadata['created_by'] = self.request.user.username

        # Try to attach store_id to metadata: prefer POST value, otherwise use user's single store if available
        store_id = self.request.POST.get('store_id')
        if store_id and store_id.isdigit():
            form.instance.metadata['store_id'] = int(store_id)
        else:
            try:
                user_stores = Store.objects.filter(owner=self.request.user)
                if user_stores.count() == 1:
                    form.instance.metadata['store_id'] = user_stores.first().id
            except Exception:
                pass
        
        response = super().form_valid(form)
        
        # Send notification
        send_delivery_notification(
            delivery=self.object,
            notification_type='delivery_created',
            recipient=self.request.user
        )
        
        return response
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


# Protect create view as well
CreateDeliveryView.dispatch = method_decorator(seller_or_delivery_or_admin_required)(CreateDeliveryView.dispatch)


@method_decorator(seller_or_delivery_or_admin_required, name='dispatch')
class UpdateDeliveryStatusView(LoginRequiredMixin, UpdateView):
    """Update delivery status"""
    model = DeliveryRequest
    fields = ['status']
    template_name = 'delivery/update_status.html'
    
    def get_success_url(self):
        return reverse_lazy('delivery:delivery_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        # Ensure self.object is populated
        self.object = self.get_object()
        old_status = self.object.status
        new_status = form.cleaned_data['status']
        
        # Validate status transition
        valid_transitions = self.get_valid_transitions(old_status)
        if new_status not in valid_transitions:
            form.add_error('status', f'Invalid status transition from {old_status} to {new_status}')
            return self.form_invalid(form)
        
        # Update status with notes
        notes = self.request.POST.get('notes', '')
        self.object.update_status(new_status, notes, changed_by_user=self.request.user)

        # Try to update ecommerce order and enqueue external sync
        try:
            from . import integration as integration_module
            try:
                integration_module.update_order_from_delivery(self.object)
            except Exception:
                pass
        except Exception:
            pass

        try:
            from . import tasks as delivery_tasks
            try:
                delivery_tasks.sync_with_external_system.delay(self.object.id)
            except Exception:
                delivery_tasks.sync_with_external_system(self.object.id)
        except Exception:
            pass

        return redirect(self.get_success_url())
    
    def get_valid_transitions(self, current_status):
        """Define valid status transitions"""
        transitions = {
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
        return transitions.get(current_status, [])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['delivery'] = self.get_object()
        except Exception:
            context['delivery'] = getattr(self, 'object', None)
        context['status_choices'] = DeliveryRequest.STATUS_CHOICES
        # Provide the set of valid transitions for the current delivery status
        try:
            current = None
            if context.get('delivery'):
                current = context['delivery'].status
            elif getattr(self, 'object', None):
                current = self.object.status
            context['valid_transitions'] = self.get_valid_transitions(current) if current is not None else []
        except Exception:
            context['valid_transitions'] = []
        return context


    # UpdateDeliveryStatusView dispatch is protected via @method_decorator above


@method_decorator(delivery_person_required, name='dispatch')
class DriverDashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard for delivery drivers"""
    template_name = 'delivery/driver_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        driver = self.request.user.delivery_person
        
        # Get today's assignments
        today = timezone.now().date()
        context['today_assignments'] = DeliveryRequest.objects.filter(
            delivery_person=driver,
            status__in=['assigned', 'picked_up', 'in_transit', 'out_for_delivery'],
            created_at__date=today
        ).order_by('priority', 'estimated_delivery_time')
        
        # Get pending pickups
        context['pending_pickups'] = DeliveryRequest.objects.filter(
            delivery_person=driver,
            status='assigned'
        ).order_by('estimated_delivery_time')
        
        # Get recent deliveries
        context['recent_deliveries'] = DeliveryRequest.objects.filter(
            delivery_person=driver,
            status='delivered'
        ).order_by('-actual_delivery_time')[:10]
        
        # Driver statistics
        context['driver_stats'] = {
            'total': driver.total_deliveries,
            'completed': driver.completed_deliveries,
            'success_rate': (driver.completed_deliveries / driver.total_deliveries * 100) if driver.total_deliveries > 0 else 0,
            'rating': driver.rating,
            'weekly_earnings': self.calculate_weekly_earnings(driver),
        }
        
        # Update driver status if needed
        if self.request.GET.get('status'):
            new_status = self.request.GET.get('status')
            if new_status in dict(DeliveryPerson.STATUS_CHOICES):
                driver.current_status = new_status
                driver.is_available = (new_status == 'available')
                driver.save()
        
        return context
    
    def calculate_weekly_earnings(self, driver):
        """Calculate weekly earnings for driver"""
        week_ago = timezone.now() - timedelta(days=7)
        
        earnings = DeliveryRequest.objects.filter(
            delivery_person=driver,
            status='delivered',
            actual_delivery_time__gte=week_ago
        ).aggregate(
            total=Sum('delivery_fee')
        )['total'] or 0
        
        # Assume driver gets 70% of delivery fee
        return earnings * Decimal('0.7')


@login_required
@delivery_person_required
def update_driver_location(request):
    """Update driver's current location"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lat = data.get('latitude')
            lng = data.get('longitude')
            
            if lat and lng:
                driver = request.user.delivery_person
                driver.update_location(lat, lng)
                
                return JsonResponse({
                    'success': True,
                    'message': 'Location updated successfully'
                })
        except (json.JSONDecodeError, ValueError):
            pass
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request'
    }, status=400)


@login_required
def track_delivery(request, tracking_number):
    """Public tracking page"""
    delivery = get_object_or_404(DeliveryRequest, tracking_number=tracking_number)
    
    # Get status history
    status_history = delivery.status_history.all().order_by('-created_at')
    
    # Calculate estimated delivery time
    estimated_time = None
    if delivery.estimated_delivery_time:
        estimated_time = delivery.estimated_delivery_time
    
    context = {
        'delivery': delivery,
        'status_history': status_history,
        'estimated_time': estimated_time,
        'show_details': True,  # Public can see basic info
    }
    
    return render(request, 'delivery/tracking.html', context)


@login_required
def submit_proof(request, pk):
    """Handle proof of delivery submissions (files, signatures, codes)."""
    delivery = get_object_or_404(DeliveryRequest, pk=pk)

    # Permission: only staff, delivery_person assigned, or store owner may submit proof
    user = request.user
    allowed = False
    if user.is_staff or user.is_superuser:
        allowed = True
    if hasattr(user, 'delivery_person') and delivery.delivery_person and delivery.delivery_person == user.delivery_person:
        allowed = True
    try:
        from storefront.models import Store
        stores = Store.objects.filter(owner=user)
        if stores.exists() and isinstance(delivery.metadata, dict):
            sid = delivery.metadata.get('store_id')
            if sid and any(str(s.id) == str(sid) or s.id == int(sid) for s in stores):
                allowed = True
    except Exception:
        pass

    if not allowed:
        messages.error(request, 'You do not have permission to submit proof for this delivery.')
        return redirect('delivery:delivery_detail', pk=delivery.pk)

    if request.method == 'POST':
        proof_type = request.POST.get('proof_type')
        notes = request.POST.get('notes', '')
        verification_code = request.POST.get('verification_code')
        recipient_name = request.POST.get('recipient_name')
        recipient_id_type = request.POST.get('recipient_id_type')
        recipient_id_number = request.POST.get('recipient_id_number')

        file = request.FILES.get('file')
        signature_data = request.POST.get('signature_data')

        proof = DeliveryProof.objects.create(
            delivery_request=delivery,
            proof_type=proof_type or 'photo',
            file=file if file else None,
            signature_data=signature_data or None,
            verification_code=verification_code or None,
            recipient_name=recipient_name or None,
            recipient_id_type=recipient_id_type or None,
            recipient_id_number=recipient_id_number or None,
            notes=notes or ''
        )

        # Mark delivery metadata/proof_of_delivery for reference
        try:
            meta = delivery.metadata or {}
            meta['proof'] = meta.get('proof', [])
            meta['proof'].append({'id': proof.id, 'type': proof.proof_type})
            delivery.metadata = meta
            delivery.save(update_fields=['metadata'])
        except Exception:
            pass

        messages.success(request, 'Proof of delivery submitted successfully.')
        return redirect('delivery:delivery_detail', pk=delivery.pk)

    # If not POST, redirect back
    return redirect('delivery:delivery_detail', pk=delivery.pk)

def generate_weekly_report(request):
    """Generate weekly delivery report"""
    from datetime import timedelta
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    
    base_qs = _get_deliveries_for_user(request.user, request=request)
    deliveries = base_qs.filter(
        created_at__date__gte=start_of_week
    ).select_related('delivery_person', 'delivery_service')
    
    summary = {
        'total': deliveries.count(),
        'delivered': deliveries.filter(status='delivered').count(),
        'pending': deliveries.filter(status__in=['pending', 'accepted', 'assigned']).count(),
        'in_transit': deliveries.filter(status__in=['picked_up', 'in_transit', 'out_for_delivery']).count(),
        'failed': deliveries.filter(status='failed').count(),
        'revenue': deliveries.filter(payment_status='paid').aggregate(
            total=Sum('total_amount')
        )['total'] or 0,
    }
    
    context = {
        'report_type': 'weekly',
        'start_date': start_of_week,
        'end_date': today,
        'deliveries': deliveries,
        'summary': summary,
    }
    
    if request.GET.get('format') == 'csv':
        return export_to_csv(deliveries, f'weekly_report_{start_of_week}_to_{today}.csv')
    
    return render(request, 'delivery/reports/weekly_report.html', context)


def generate_monthly_report(request):
    """Generate monthly delivery report"""
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    
    base_qs = _get_deliveries_for_user(request.user, request=request)
    deliveries = base_qs.filter(
        created_at__date__gte=start_of_month
    ).select_related('delivery_person', 'delivery_service')
    
    summary = {
        'total': deliveries.count(),
        'delivered': deliveries.filter(status='delivered').count(),
        'pending': deliveries.filter(status__in=['pending', 'accepted', 'assigned']).count(),
        'in_transit': deliveries.filter(status__in=['picked_up', 'in_transit', 'out_for_delivery']).count(),
        'failed': deliveries.filter(status='failed').count(),
        'revenue': deliveries.filter(payment_status='paid').aggregate(
            total=Sum('total_amount')
        )['total'] or 0,
    }
    
    context = {
        'report_type': 'monthly',
        'start_date': start_of_month,
        'end_date': today,
        'deliveries': deliveries,
        'summary': summary,
    }
    
    if request.GET.get('format') == 'csv':
        return export_to_csv(deliveries, f'monthly_report_{start_of_month}_to_{today}.csv')
    
    return render(request, 'delivery/reports/monthly_report.html', context)


def generate_driver_report(request):
    """Generate driver performance report"""
    base_qs = _get_deliveries_for_user(request.user, request=request)
    # Drivers relevant to the user's deliveries
    drivers = DeliveryPerson.objects.filter(assignments__in=base_qs).distinct()

    if request.GET.get('driver_id'):
        drivers = drivers.filter(id=request.GET.get('driver_id'))

    driver_stats = []
    for driver in drivers:
        assignments = driver.assignments.filter(id__in=base_qs.values_list('id', flat=True))
        completed = assignments.filter(status='delivered')
        
        stats = {
            'driver': driver,
            'total_assignments': assignments.count(),
            'completed': completed.count(),
            'completion_rate': (completed.count() / assignments.count() * 100) if assignments.count() > 0 else 0,
            'avg_rating': completed.aggregate(avg=Avg('rating__rating'))['avg'] or 0,
            'total_revenue': completed.aggregate(total=Sum('delivery_fee'))['total'] or 0,
        }
        driver_stats.append(stats)
    
    context = {
        'report_type': 'driver',
        'driver_stats': driver_stats,
        'drivers': drivers,
    }
    
    return render(request, 'delivery/reports/driver_report.html', context)


def generate_zone_report(request):
    """Generate delivery zone performance report"""
    zones = DeliveryZone.objects.filter(is_active=True)
    
    base_qs = _get_deliveries_for_user(request.user, request=request)
    zone_stats = []
    for zone in zones:
        deliveries = base_qs.filter(delivery_zone=zone)
        
        stats = {
            'zone': zone,
            'total_deliveries': deliveries.count(),
            'completed': deliveries.filter(status='delivered').count(),
            'pending': deliveries.filter(status__in=['pending', 'accepted', 'assigned']).count(),
            'total_revenue': deliveries.aggregate(total=Sum('delivery_fee'))['total'] or 0,
            'avg_delivery_fee': deliveries.aggregate(avg=Avg('delivery_fee'))['avg'] or 0,
        }
        zone_stats.append(stats)
    
    context = {
        'report_type': 'zone',
        'zone_stats': zone_stats,
    }
    
    return render(request, 'delivery/reports/zone_report.html', context)

@login_required
@seller_or_delivery_or_admin_required
def delivery_reports(request):
    """Generate delivery reports"""
    report_type = request.GET.get('type', 'daily')
    
    if report_type == 'daily':
        return generate_daily_report(request)
    elif report_type == 'weekly':
        return generate_weekly_report(request)
    elif report_type == 'monthly':
        return generate_monthly_report(request)
    elif report_type == 'driver':
        return generate_driver_report(request)
    elif report_type == 'zone':
        return generate_zone_report(request)
    
    return render(request, 'delivery/reports/daily_report.html')


def generate_daily_report(request):
    """Generate daily delivery report"""
    date = request.GET.get('date', timezone.now().date())
    
    if isinstance(date, str):
        date = datetime.strptime(date, '%Y-%m-%d').date()
    
    base_qs = _get_deliveries_for_user(request.user, request=request)
    deliveries = base_qs.filter(
        created_at__date=date
    ).select_related('delivery_person', 'delivery_service')
    
    # Summary statistics
    summary = {
        'total': deliveries.count(),
        'delivered': deliveries.filter(status='delivered').count(),
        'pending': deliveries.filter(status__in=['pending', 'accepted', 'assigned']).count(),
        'in_transit': deliveries.filter(status__in=['picked_up', 'in_transit', 'out_for_delivery']).count(),
        'failed': deliveries.filter(status='failed').count(),
        'revenue': deliveries.filter(payment_status='paid').aggregate(
            total=Sum('total_amount')
        )['total'] or 0,
    }
    
    context = {
        'report_type': 'daily',
        'date': date,
        'deliveries': deliveries,
        'summary': summary,
    }
    
    if request.GET.get('format') == 'csv':
        return export_to_csv(deliveries, f'daily_report_{date}.csv')
    
    return render(request, 'delivery/reports/daily_report.html', context)


@require_POST
@login_required
def bulk_update_status(request):
    """Bulk update delivery status"""
    try:
        data = json.loads(request.body)
        delivery_ids = data.get('delivery_ids', [])
        new_status = data.get('status')
        notes = data.get('notes', '')
        
        if not delivery_ids or not new_status:
            return JsonResponse({'error': 'Missing required fields'}, status=400)
        
        # Get deliveries
        deliveries = DeliveryRequest.objects.filter(id__in=delivery_ids)
        
        # Update each delivery
        updated = 0
        for delivery in deliveries:
            old_status = delivery.status
            if new_status != old_status:
                delivery.update_status(new_status, notes, changed_by_user=request.user)
                updated += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Updated {updated} deliveries',
            'updated': updated
        })
        
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def delivery_analytics(request):
    """Delivery analytics dashboard"""
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
    
    # Get deliveries for the period (scoped to user)
    base_deliveries = _get_deliveries_for_user(user, request=request)
    deliveries = base_deliveries.filter(created_at__gte=start_date)
    
    # Calculate metrics
    total_deliveries = deliveries.count()
    completed = deliveries.filter(status='delivered').count()
    success_rate = (completed / total_deliveries * 100) if total_deliveries > 0 else 0
    
    # Average delivery time in hours
    completed_deliveries = deliveries.filter(
        status='delivered',
        actual_delivery_time__isnull=False,
        pickup_time__isnull=False
    )
    
    avg_time_hours = None
    if completed_deliveries.exists():
        total_hours = 0
        count = 0
        for delivery in completed_deliveries:
            if delivery.actual_delivery_time and delivery.pickup_time:
                duration = delivery.actual_delivery_time - delivery.pickup_time
                total_hours += duration.total_seconds() / 3600
                count += 1
        
        if count > 0:
            avg_time_hours = total_hours / count
    
    # Revenue
    revenue = deliveries.filter(
        payment_status='paid'
    ).aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    # Top drivers (only for admin/staff)
    top_drivers = None
    if user.is_staff or user.is_superuser:
        top_drivers = DeliveryPerson.objects.annotate(
            delivery_count=Count('assignments'),
            avg_rating=Avg('assignments__rating__rating')
        ).order_by('-delivery_count')[:5]
    
    # Zone performance - calculate properly for all users
    try:
        from storefront.models import Store
        stores = Store.objects.filter(owner=user)
        
        if user.is_staff or user.is_superuser:
            # Admin sees all zones
            zone_performance = DeliveryZone.objects.annotate(
                delivery_count=Count('deliveryrequest'),
                avg_fee=Avg('deliveryrequest__delivery_fee'),
                total_revenue=Sum('deliveryrequest__delivery_fee')
            ).order_by('-delivery_count')
        elif stores.exists():
            # Seller sees zones for their stores
            store_ids = [store.id for store in stores]
            
            # Get zone IDs that have deliveries from seller's stores
            zone_ids = base_deliveries.filter(
                delivery_zone__isnull=False
            ).values_list('delivery_zone_id', flat=True).distinct()
            
            # Get zones with performance data
            zone_performance = DeliveryZone.objects.filter(
                id__in=zone_ids
            ).annotate(
                delivery_count=Count('deliveryrequest', filter=Q(
                    deliveryrequest__id__in=base_deliveries.values_list('id', flat=True)
                )),
                avg_fee=Avg('deliveryrequest__delivery_fee', filter=Q(
                    deliveryrequest__id__in=base_deliveries.values_list('id', flat=True)
                )),
                total_revenue=Sum('deliveryrequest__delivery_fee', filter=Q(
                    deliveryrequest__id__in=base_deliveries.values_list('id', flat=True)
                ))
            ).order_by('-delivery_count')
        else:
            zone_performance = DeliveryZone.objects.none()
    except Exception:
        zone_performance = DeliveryZone.objects.none()
    
    # Status distribution for chart
    status_distribution = deliveries.values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    # Weekly activity for chart
    weekly_activity = []
    for i in range(7):
        date = (timezone.now() - timedelta(days=i)).date()
        count = deliveries.filter(created_at__date=date).count()
        weekly_activity.append({
            'date': date.strftime('%Y-%m-%d'),
            'day': date.strftime('%a'),
            'count': count
        })
    weekly_activity.reverse()  # Show oldest to newest
    
    context = {
        'period': period,
        'total_deliveries': total_deliveries,
        'completed_deliveries': completed,
        'success_rate': round(success_rate, 2),
        'average_delivery_time_hours': round(avg_time_hours, 2) if avg_time_hours else None,
        'revenue': revenue,
        'top_drivers': top_drivers,
        'zone_performance': zone_performance,
        'status_distribution': list(status_distribution),
        'weekly_activity': weekly_activity,
        'start_date': start_date,
        'end_date': timezone.now(),
        'is_admin': user.is_staff or user.is_superuser,
        'is_delivery_person': hasattr(user, 'delivery_person'),
    }
    
    return render(request, 'delivery/reports/analytics.html', context)

def export_to_csv(queryset, filename):
    """Export queryset to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    
    # Write headers
    writer.writerow([
        'Tracking Number', 'Order ID', 'Status', 'Recipient Name',
        'Recipient Phone', 'Delivery Fee', 'Payment Status',
        'Created At', 'Delivered At', 'Driver'
    ])
    
    # Write data
    for item in queryset:
        writer.writerow([
            item.tracking_number,
            item.order_id,
            item.get_status_display(),
            item.recipient_name,
            item.recipient_phone,
            item.delivery_fee,
            item.get_payment_status_display(),
            item.created_at.strftime('%Y-%m-%d %H:%M'),
            item.actual_delivery_time.strftime('%Y-%m-%d %H:%M') if item.actual_delivery_time else '',
            item.delivery_person.user.get_full_name() if item.delivery_person else ''
        ])
    
    return response